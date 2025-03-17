<template>
    <div class="main-view" :class="{ 'disabled-content': showBranchModal }">
        <header class="header">
            <div ref="detectOutsideClick" class="left-section">
                <button @click="toggleMenu" class="menu-btn">
                    <font-awesome-icon icon="fa-solid fa-bars" />
                </button>
                <h1>COFACTORY</h1>
                <div  v-if="menuOpen" class="dropdown-menu">
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
        <CriteriaModal v-if="showCriteriaModal" :title="modalTitle" :criteria="criteria" @confirm="handleModalConfirm"
            @close="closeCriteriaModal" />

        <RemoveMachinesModal v-if="showRemoveMachinesModal" :machines="availableMachines" :processes="processes"
            @confirm="handleRemoveMachinesConfirm" @close="closeRemoveMachinesModal" />

        <RemoveBoMsModal v-if="showRemoveBoMsModal" :BoMs="inputBoMs" @confirm="handleRemoveBoMsConfirm"
            @close="closeRemoveBoMsModal" />

        <ResultsModal v-if="showResultsModal" @confirm="handleResultsConfirm" @cancel="closeResultsModal"
            @rerun="rerunPlan" />

        <MissingItemsModal v-if="missingItemsData[userID]?.shouldShow"
            :noRoutings="missingItemsData[userID]?.noRoutings || []" :noBoms="missingItemsData[userID]?.noBoms || []"
            @close="closeMissingItemsModal" />

        <PlanHistoryPage v-if="showPlanHistory" @close="closePlanHistoryPage" />
    </div>

    <!--<div v-if="showBranchModal" class="modal-overlay">
        <BranchSelectionModal @confirm="handleBranchSelection" />
    </div>-->
</template>

<script lang="ts">
import GanttChart from "@/components/GanttChart.vue";
import CriteriaModal from "@/components/CriteriaModal.vue";
import RemoveMachinesModal from "@/components/RemoveMachinesModal.vue";
import RemoveBoMsModal from "@/components/RemoveBoMsModal.vue";
import ResultsModal from "@/components/ResultsModal.vue";
import MissingItemsModal from "@/components/MissingItemsModal.vue";
//import BranchSelectionModal from "@/components/BranchSelectionModal.vue";
import PlanHistoryPage from "@/components/PlanHistoryPage.vue";

export default {
    components: { GanttChart, CriteriaModal, RemoveMachinesModal, RemoveBoMsModal, ResultsModal, MissingItemsModal, PlanHistoryPage },
    data() {
        return {
            userID: null as any,
            showBranchModal: true,
            showCriteriaModal: false,
            showRemoveMachinesModal: false,
            showRemoveBoMsModal: false,
            showResultsModal: false,
            showGanttChart: false,
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
            missingItemsData: {},
            bomsRemoved: false,
            isAlgorithmRunning: false,
            renderKey: 0,
            menuOpen: false,
            apiUrl: `${import.meta.env.VITE_FLASK_HOST}:${import.meta.env.VITE_FLASK_PORT}`,
        };
    },
    mounted() {
        window.addEventListener("beforeunload", this.handlePageUnload);
        document.addEventListener('click', this.handleClickOutside);
        // Check for URL parameters
        this.checkUrlParameters();
    },
    beforeDestroy() {
        window.removeEventListener("beforeunload", this.handlePageUnload);
        document.removeEventListener('click', this.handleClickOutside);
    },
    methods: {
        handleClickOutside(event) {
            if (!this.$refs.detectOutsideClick.contains(event.target)) {
                this.menuOpen = false;
            }
        },
        // New method to check URL parameters
        checkUrlParameters() {
            // Get URL search parameters
            const urlParams = new URLSearchParams(window.location.search);

            // Check for BRANCH and USER parameters
            const branch = urlParams.get('BRANCH');
            const userId = urlParams.get('USER');

            if (branch && userId) {
                // Map BRANCH parameter to correct database name
                let dbBranch;
                if (branch === 'COFPT') {
                    dbBranch = 'COFACTORY_PT';
                } else if (branch === 'COFGR') {
                    dbBranch = 'COFACTORY_GR';
                }

                this.selectBranchWithParams(dbBranch, userId);
            } else {
                console.error("Branch or userId missing in URL parameters.");
            }

        },
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
        async selectBranchWithParams(branch, userId) {

            try {
                const response = await fetch(`${this.apiUrl}/selectBranch?user_id=${this.userID}`, {
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
                alert(error);
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

                const response = await fetch(`${this.apiUrl}/uploadInputFile?user_id=${this.userID}`, {
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

            await fetch(`${this.apiUrl}/criteria?user_id=${this.userID}`, {
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
                const response = await fetch(`${this.apiUrl}/machines`, {
                    method: 'GET',
                    credentials: 'include',
                });
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
                const response = await fetch(`${this.apiUrl}/BoMs`, {
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

            fetch(`${this.apiUrl}/removeMachines?user_id=${this.userID}`, {
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

            fetch(`${this.apiUrl}/removeBoMs?user_id=${this.userID}`, {
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

            if (isReady) {
                fetch(`${this.apiUrl}/createData?user_id=${this.userID}`, {
                    method: 'POST',
                    credentials: 'include',
                })
                    .then(response => response.json())
                    .then((data) => {
                        if (!this.missingItemsData[this.userID]) {
                            this.missingItemsData[this.userID] = {
                                noRoutings: [],
                                noBoms: [],
                                shouldShow: false
                            };
                        }

                        // Update the user's missing items
                        if (data.no_routings && data.no_routings.length > 0) {
                            this.missingItemsData[this.userID].noRoutings = data.no_routings;
                        }

                        if (data.no_bom && data.no_bom.length > 0) {
                            this.missingItemsData[this.userID].noBoms = data.no_bom;
                        }

                        // Set flag to show modal for this user
                        if (this.missingItemsData[this.userID].noRoutings.length > 0 ||
                            this.missingItemsData[this.userID].noBoms.length > 0) {
                            this.missingItemsData[this.userID].shouldShow = true;
                        }

                        this.isAlgorithmRunning = true;
                        fetch(`${this.apiUrl}/runAlgorithm?user_id=${this.userID}`, {
                            method: 'POST',
                            credentials: 'include',
                        })
                            .then(response => response.json())
                            .then(() => {
                                // Start polling for status
                                this.pollAlgorithmStatus();
                            })
                            .catch((error) => {
                                console.error("Erro na execução do algoritmo:", error);
                                if (error && error.message) {
                                    alert(error.message);
                                } else {
                                    alert("Ocorreu um erro na execução do algoritmo.");
                                }

                                this.isAlgorithmRunning = false;
                            });
                    })
                    .catch((error) => {
                        console.error("Erro na obtenção dos itens não existentes:", error);
                    });
            }
        },
        pollAlgorithmStatus() {
            const checkStatus = () => {
                // UserID in URL to make sure it's always available
                fetch(`${this.apiUrl}/algorithmStatus?user_id=${this.userID}`, {
                    credentials: 'include',
                })
                    .then(response => response.json())
                    .then(data => {
                        if (data.status === 'completed') {
                            this.isAlgorithmRunning = false;
                            this.showResultsModal = true;
                        } else if (data.status === 'error' || data.status === 'aborted') {
                            this.isAlgorithmRunning = false;
                            console.error("Algorithm failed:", data.message);
                            alert("Ocorreu um erro na execução do algoritmo. Por favor tente novamente.");
                        } else if (data.status === 'not_running') {
                            // Algorithm is no longer running
                            this.isAlgorithmRunning = false;
                        } else if (data.status === 'running') {
                            this.isAlgorithmRunning = true;
                            // Still running, check again in 2 seconds
                            setTimeout(checkStatus, 2000);
                        } else {
                            // Still running, check again in 2 seconds
                            setTimeout(checkStatus, 2000);
                        }
                    })
                    .catch(error => {
                        console.error("Erro na verificação do estado do algoritmo:", error);
                        if (this.isAlgorithmRunning) {
                            setTimeout(checkStatus, 5000); // Retry with longer delay
                            alert("Ocorreu um erro na execução do algoritmo. Por favor tente novamente.");
                        }
                    });
            };

            // Start checking
            checkStatus();
        },
        closeMissingItemsModal() {
            if (this.missingItemsData[this.userID]) {
                this.missingItemsData[this.userID].shouldShow = false;
            }
        },
        handleResultsConfirm() {
            this.showResultsModal = false;
            fetch(`${this.apiUrl}/saveResults?user_id=${this.userID}`, {
                method: 'POST',
                credentials: 'include',
            })
                .then(response => {
                    if (!response.ok) {
                        throw new Error("Falha no download dos ficheiros.");
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
                    console.log("Resultados guardados com sucesso:", data);
                    this.refreshGanttChart();
                })
                .catch((error) => {
                    console.error("Erro no armazenamento dos resultados:", error);
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
                    const url = `${this.apiUrl}/abortAlgorithm`;
                    const data = new Blob([], { type: 'text/plain' });
                    navigator.sendBeacon(url, data);
                } catch (error) {
                    console.error("Erro no envio do sinal de termino do algoritmo:", error);
                }
            }
            event.preventDefault();
        },
        refreshGanttChart() {
            this.renderKey++; // Forces re-rendering of GanttChart
        },
        deleteFileRequest() {
            fetch(`${this.apiUrl}/deleteInputFile?user_id=${this.userID}`, {
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
    justify-content: space-between;
    /* Keeps the button on the right */
    background-color: #4CAF50;
    color: white;
    padding: 10px 20px;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    margin-top: 50px;
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
