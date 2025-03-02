<template>
    <div class="main-view" :class="{ 'disabled-content': showBranchModal }">
        <header class="header">
            <div class="left-section">
                <button @click="toggleMenu" class="menu-btn">
                    <font-awesome-icon icon="fa-solid fa-bars" />
                </button>
                <h1>COFACTORY</h1>
                <div v-if="menuOpen" class="dropdown-menu">
                    <ul>
                        <li @click="createNewPlan">Criar Novo Plano</li>
                        <li @click="openPlanHistoryPage">Histórico de Planos</li> 
                    </ul>
                </div>
            </div>
            <!--<button @click="createNewPlan" class="create-plan-btn">Criar Novo Plano</button>-->
        </header>

        <div class="gantt-container" v-if="showGanttChart">
            <GanttChart :isLoading="isAlgorithmRunning" :key="renderKey" />
        </div>

        <!-- Other modals -->
        <CriteriaModal v-if="showCriteriaModal" :title="modalTitle" :criteria="criteria"
            @confirm="handleModalConfirm" @close="closeCriteriaModal"/>

        <RemoveMachinesModal v-if="showRemoveMachinesModal" :machines="availableMachines" :processes="processes"
            @confirm="handleRemoveMachinesConfirm" @close="closeRemoveMachinesModal" />

        <RemoveBoMsModal v-if="showRemoveBoMsModal" :BoMs="inputBoMs" @confirm="handleRemoveBoMsConfirm"
            @close="closeRemoveBoMsModal" />

        <ResultsModal v-if="showResultsModal" @confirm="handleResultsConfirm" @cancel="closeResultsModal"
            @rerun="rerunPlan" />

        <MissingItemsModal v-if="showMissingItemsModal" :noRoutings="noRoutings" :noBoms="noBoms"
            @close="closeMissingItemsModal" />

        <PlanHistoryPage v-if="showPlanHistory" @close="closePlanHistoryPage" />
    </div>

    <div v-if="showBranchModal" class="modal-overlay">
        <BranchSelectionModal @confirm="handleBranchSelection" />
    </div>
</template>

<script lang="ts">
import GanttChart from "@/components/GanttChart.vue";
import CriteriaModal from "@/components/CriteriaModal.vue";
import RemoveMachinesModal from "@/components/RemoveMachinesModal.vue";
import RemoveBoMsModal from "@/components/RemoveBoMsModal.vue";
import ResultsModal from "@/components/ResultsModal.vue";
import MissingItemsModal from "@/components/MissingItemsModal.vue";
import BranchSelectionModal from "@/components/BranchSelectionModal.vue";
import PlanHistoryPage from "@/components/PlanHistoryPage.vue";

export default {
    components: { GanttChart, CriteriaModal, RemoveMachinesModal, RemoveBoMsModal, ResultsModal, MissingItemsModal, BranchSelectionModal, PlanHistoryPage },
    data() {
        return {
            userID: null as any,
            showBranchModal: true,
            showCriteriaModal: false,
            showRemoveMachinesModal: false,
            showRemoveBoMsModal: false,
            showResultsModal: false,
            showGanttChart: false,
            showMissingItemsModal: false,
            showPlanHistory: false,
            modalTitle: "",
            criteria: ["Remover Máquinas", "Organizar por Melhor Cycle Time", "Sequenciamento por Diâmetro", "Consumir Stock disponível", "Menor Número de Mudanças", "Desativar BoMs"],
            selectedCriteria: {},
            selectedFile: null as any,
            availableMachines: [],
            processes: [],
            inputBoMs: null as any,
            criteriaSelected: false,
            machinesRemoved: false,
            bomsRemoved: false,
            isAlgorithmRunning: false,
            noRoutings: [],
            noBoms: [],
            renderKey: 0,
            menuOpen: false,
        };
    },
    mounted() {
        window.addEventListener("beforeunload", this.handlePageUnload);
    },
    beforeDestroy() {
        window.removeEventListener("beforeunload", this.handlePageUnload);
    },
    methods: {
        toggleMenu() {
            this.menuOpen = !this.menuOpen;
        },
        openPlanHistoryPage() {
            this.showPlanHistory = true;
            this.menuOpen = false;
            this.showGanttChart = false;
        },
        closePlanHistoryPage() {
            this.showPlanHistory = false;
            this.showGanttChart = true;
        },
        async handleBranchSelection({branch, userId}) {
            try {
                const response = await fetch('http://localhost:5001/selectBranch', {
                    method: 'POST',
                    credentials: 'include',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ branch, userId }),
                });

                const data = await response.json();
                if (response.ok) {
                    this.userID = userId;
                    this.showBranchModal = false; 
                    this.showGanttChart = true;
                    console.log(data.message);
                } else {
                    alert(data.message);
                }
            } catch (error) {
                console.error("Erro ao selecionar a unidade de produção:", error);
                alert("Ocorreu um erro ao selecionar a unidade de produção.");
            }
        },
        async createNewPlan() {
            this.menuOpen = false;
            const openFilePicker = async () => {
                if (!window.showOpenFilePicker) {
                    return new Promise((resolve) => {
                        const input = document.createElement("input");
                        input.type = "file";
                        input.accept = ".xlsx";
                        input.onchange = (event) => {
                            const file = event.target.files[0];
                            resolve(file);
                        };
                        input.click();
                    });
                }

                try {
                    const [fileHandle] = await window.showOpenFilePicker({
                        types: [
                            {
                                description: "Excel Files",
                                accept: { "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"] },
                            },
                        ],
                        multiple: false,
                    });
                    return await fileHandle.getFile();
                } catch (error) {
                    console.error("Erro na seleção do ficheiro:", error);
                    return null;
                }
            };

            try {
                const file = await openFilePicker();
                if (!file) {
                    alert("Nenhum ficheiro selecionado.");
                    return;
                }
                
                this.selectedFile = file;

                const formData = new FormData();
                formData.append("file", file);

                const response = await fetch("http://localhost:5001/uploadInputFile", {
                    method: "POST",
                    credentials: 'include',
                    body: formData,
                })
                
                const result = await response.json();
                if (response.ok) {
                    this.criteriaModal({
                        title: "Critérios",
                        criteria: this.criteria,
                    });
                } else {
                    alert(result.message);
                }

            } catch (error) {
                console.error("Error:", error);
                alert("Ocorreu um erro. Por favor tente outra vez.");
            }
        },
        async handleModalConfirm(selectedCriteria) {
            console.log("Critérios:", selectedCriteria);
            this.criteriaSelected = true;

            await fetch("http://localhost:5001/criteria", {
                method: "POST",
                credentials: 'include',
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({ selectedCriteria, allCriteria: this.criteria }),
            })
                .then((response) => response.json())
                .catch(() => {
                    alert("Erro no processamento dos critérios. Por favor tente outra vez.");
                });

            this.showCriteriaModal = false;

            if (selectedCriteria[0]) {
                await this.fetchMachines();
                this.showRemoveMachinesModal = true;
            }

            if (selectedCriteria[5] && !this.showRemoveMachinesModal) {
                await this.fetchBoMs();
                this.showRemoveBoMsModal = true;
            }

            this.selectedCriteria = selectedCriteria;
            this.checkIfReadyToFinalize();
        },
        closeCriteriaModal() {
            this.deleteFileRequest();
            this.showCriteriaModal = false;
        },
        async fetchMachines() {
            try {
                const response = await fetch("http://localhost:5001/machines");
                const data = await response.json();
                if (response.ok) {
                    this.availableMachines = data.machines.map(machine => machine.name);
                    this.processes = data.processes;
                } else {
                    alert("Erro ao solicitação das máquinas. Por favor tente outra vez.");
                }
            } catch (error) {
                alert("Erro na solicitação das máquinas. Por favor tente outra vez.");
            }
        },
        async fetchBoMs() {
            try {
                const response = await fetch("http://localhost:5001/BoMs", {
                    method: 'GET',
                    credentials: 'include',
                });
                const data = await response.json();
                if (response.ok) {
                    this.inputBoMs = data.item_BoMs;
                } else {
                    alert("Erro na solicitação das BOM's. Por favor tente outra vez.");
                }
            } catch (error) {
                alert("Erro na solicitação das BOM's. Por favor tente outra vez.");
            }
        },
        handleRemoveMachinesConfirm(selectedMachines) {
            console.log("Máquinas selecionadas para remoção:", selectedMachines);
            this.showRemoveMachinesModal = false;
            this.machinesRemoved = true;

            fetch("http://localhost:5001/removeMachines", {
                method: "POST",
                credentials: 'include',
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(selectedMachines),
            })
                .then((response) => response.json())
                .then(() => {
                    if (this.selectedCriteria[5]) {
                        this.fetchBoMs();
                        this.showRemoveBoMsModal = true;
                    } else {
                        this.checkIfReadyToFinalize();
                    }
                })
                .catch((error) => {
                    console.error("Erro na solicitação de remoção:", error);
                });
            
        },
        closeRemoveMachinesModal() {
            this.deleteFileRequest();
            this.showRemoveMachinesModal = false;
        },
        handleRemoveBoMsConfirm(selectedBoMs) {
            console.log("BOM's selecionadas para remoção:", selectedBoMs);
            this.showRemoveBoMsModal = false;
            this.bomsRemoved = true;

            fetch("http://localhost:5001/removeBoMs", {
                method: "POST",
                credentials: 'include',
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(selectedBoMs),
            })
                .then((response) => response.json())
                .then(() => this.checkIfReadyToFinalize())
                .catch((error) => {
                    console.error("Erro na solicitação de remoção:", error);
                });
        },
        closeRemoveBoMsModal() {
            this.deleteFileRequest();
            this.showRemoveBoMsModal = false;
        },
        checkIfReadyToFinalize() {
            const isReady =
                this.criteriaSelected &&
                (!this.selectedCriteria[0] || this.machinesRemoved) &&
                (!this.selectedCriteria[5] || this.bomsRemoved);
            console.log(isReady, this.selectedCriteria);

            if (isReady) {
                fetch('http://localhost:5001/createData', {
                    method: 'POST',
                    credentials: 'include',
                })
                    .then((data) => {
                        // Check if items with no routings and/or no BoM's exist
                        if (data.no_routings && data.no_routings.length > 0) {
                            this.noRoutings = data.no_routings;
                        }

                        if (data.no_bom && data.no_bom.length > 0) {
                            this.noBoms = data.no_bom;
                        }

                        if (this.noRoutings.length > 0 || this.noBoms.length > 0) {
                            this.showMissingItemsModal = true;
                        }

                        this.isAlgorithmRunning = true;
                        fetch('http://localhost:5001/runAlgorithm', {
                            method: 'POST',
                            credentials: 'include',
                        })
                            .then(() => {
                                this.isAlgorithmRunning = false;
                                this.showResultsModal = true;
                            })
                            .catch((error) => {
                                console.error("Error running the algorithm:", error);
                                this.isAlgorithmRunning = false;
                            });
                    })
                    .catch((error) => {
                        console.error("Error getting the missing items:", error);
                    });
            }
        },
        closeMissingItemsModal() {
            this.showMissingItemsModal = false;
        },
        handleResultsConfirm() {
            this.showResultsModal = false;
            fetch("http://localhost:5001/saveResults", {
                method: 'POST',
                credentials: 'include',
            })
                .then(response => {
                    if (!response.ok) {
                      throw new Error("Failed to download the files");
                    }
                    return response.blob();  // Convert response to blob
                })
                .then(blob => {
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = 'OUTPUT_Plans.zip'; // File name
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    window.URL.revokeObjectURL(url);
                })
                .then((data) => {
                    console.log("Results saved and new data:", data);
                    this.refreshGanttChart();
                })
                .catch((error) => {
                    console.error("Error saving the results:", error);
                    alert("Erro no armazenamento do plano gerado. Por favor tente outra vez.")
                });
        },
        closeResultsModal() {
            this.deleteFileRequest();
            this.showResultsModal = false;
        },
        rerunPlan() {
            this.showResultsModal = false;
            this.criteriaModal({
                title: "Critérios",
                criteria: this.criteria,
            });
        },
        criteriaModal({ title, criteria }) {
            this.modalTitle = title;
            this.criteria = criteria;
            this.showCriteriaModal = true;
        },
        async handlePageUnload(event: Event) {
            if (this.isAlgorithmRunning) {
                try {
                    const url = "http://localhost:5001/abortAlgorithm";
                    const data = new Blob([], { type: 'text/plain' });
                    navigator.sendBeacon(url, data);
                } catch (error) {
                    console.error("Error sending abort signal:", error);
                }
            }
            event.preventDefault();
        },
        refreshGanttChart() {
            this.renderKey++; // Forces re-rendering of GanttChart
        },
        deleteFileRequest() {
            fetch("http://localhost:5001/deleteInputFile", {
                method: 'POST',
                credentials: 'include',
            })
                .catch((error) => {
                    console.error("Erro na solicitação de eliminação do ficheiro:", error);
                });
        },
    },
};
</script>

<style scoped>
/* Main view layout */
.main-view {
    display: flex;
    flex-direction: column;
    height: 100vh;
}

.header {
    display: flex;
    align-items: center;
    justify-content: space-between; /* Keeps the button on the right */
    background-color: #4CAF50;
    color: white;
    padding: 10px 20px;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
}

.header h1 {
    margin: 0;
}

/* Grouping the menu button and title together */
.left-section {
    position: relative;
    display: flex;
    align-items: center;
    gap: 15px;
}

.menu-btn {
    background: none;
    border: none;
    outline: none;
    color: inherit;
    cursor: pointer;
    font-size: 24px;
    width: 30px;
    display: flex;
    align-items: center;
    justify-content: center;
}

.menu-btn:hover {
    opacity: 0.6; 
}

.create-plan-btn {
    padding: 8px 15px;
    background-color: white;
    color: #4CAF50;
    border: none;
    border-radius: 5px;
    cursor: pointer;
    transition: 0.3s ease;
}

.create-plan-btn:hover {
    background-color: #45a049;
    color: white;
}

.dropdown-menu {
    display: block;
    position: absolute;
    top: 50px;
    left: 0;
    background-color: white;
    border: 1px solid #ddd;
    border-radius: 5px;
    box-shadow: 0px 4px 6px rgba(0, 0, 0, 0.1);
    width: 150px;
    z-index: 100;
}

.dropdown-menu ul {
    list-style: none;
    padding: 0;
    margin: 0;
}

.dropdown-menu li {
    padding: 10px;
    cursor: pointer;
    transition: background 0.3s;
}

.dropdown-menu li:hover {
    background-color: #f0f0f0;
}

/* Gantt chart container */
.gantt-container {
    flex: 1;
    background-color: #f9f9f9;
    border: 2px solid #ddd;
    border-radius: 10px;
    margin: 10px 20px;
    box-shadow: 0px 4px 8px rgba(0, 0, 0, 0.2);
    overflow: auto;
}

/* All other interactions are disabled when the branch selection is open */
.disabled-content {
    pointer-events: none;
    opacity: 0.5;
}

/* Modal overlay: remains fully interactive */
.modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background-color: rgba(0, 0, 0, 0.5);
}

.enter-user-id {
    margin-right: 60px;
}
</style>
