<template>
    <div class="main-view" :class="{ 'disabled-content': showBranchModal }">
        <header class="header">
            <h1>COFACTORY</h1>
            <button @click="createNewPlan" class="create-plan-btn">Criar Novo Plano</button>
        </header>

        <div class="gantt-container" v-if="showGanttChart">
            <GanttChart :isLoading="isAlgorithmRunning" :key="renderKey" />
        </div>

        <!-- Other modals -->
        <CriteriaModal v-if="showCriteriaModal" :title="modalTitle" :criteria="criteria"
            :confirmCallback="handleModalConfirm" />

        <RemoveMachinesModal v-if="showRemoveMachinesModal" :machines="availableMachines"
            @confirm="handleRemoveMachinesConfirm" @close="closeRemoveMachinesModal" />

        <RemoveBoMsModal v-if="showRemoveBoMsModal" :BoMs="inputBoMs" @confirm="handleRemoveBoMsConfirm"
            @close="closeRemoveBoMsModal" />

        <ResultsModal v-if="showResultsModal" @confirm="handleResultsConfirm" @cancel="closeResultsModal"
            @rerun="rerunPlan" />

        <MissingItemsModal v-if="showMissingItemsModal" :noRoutings="noRoutings" :noBoms="noBoms"
            @close="closeMissingItemsModal" />
    </div>

    <div v-if="showBranchModal" class="modal-overlay">
        <BranchSelectionModal @confirm="handleBranchSelection" />
    </div>
</template>

<script lang="ts">
import GanttChart from "@/components/GanttChart.vue";
import CriteriaModal from "@/components/Criteria.vue";
import RemoveMachinesModal from "@/components/RemoveMachinesModal.vue";
import RemoveBoMsModal from "@/components/RemoveBoMsModal.vue";
import ResultsModal from "@/components/ResultsModal.vue";
import MissingItemsModal from "@/components/MissingItemsModal.vue";
import BranchSelectionModal from "@/components/BranchSelectionModal.vue";

export default {
    components: { GanttChart, CriteriaModal, RemoveMachinesModal, RemoveBoMsModal, ResultsModal, MissingItemsModal, BranchSelectionModal },
    data() {
        return {
            showBranchModal: true,
            showCriteriaModal: false,
            showRemoveMachinesModal: false,
            showRemoveBoMsModal: false,
            showResultsModal: false,
            showGanttChart: false,
            modalTitle: "",
            criteria: ["Remover Máquinas", "Organizar por Melhor Cycle Time", "Sequenciamento por Diâmetro", "Consumir Stock disponível", "Menor Número de Mudanças", "Desativar BoMs"],
            selectedCriteria: {},
            availableMachines: [],
            inputBoMs: null as any,
            criteriaSelected: false,
            machinesRemoved: false,
            bomsRemoved: false,
            isAlgorithmRunning: false,
            showMissingItemsModal: false,
            noRoutings: [],
            noBoms: [],
            renderKey: 0,
        };
    },
    mounted() {
        window.addEventListener("beforeunload", this.handlePageUnload);
    },
    beforeDestroy() {
        window.removeEventListener("beforeunload", this.handlePageUnload);
    },
    methods: {
        async handleBranchSelection({branch, userId}) {
            try {
                const response = await fetch('http://localhost:5001/selectBranch', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ branch, userId }),
                });

                const data = await response.json();
                if (response.ok) {
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
            const showError = (message) => {
                alert(message); 
            };

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
                    showError("Nenhum ficheiro selecionado.");
                    return;
                }

                if (file.name !== "INPUT_ExtrusionPlan.xlsx") {
                    showError("Erro: Ficheiro deverá ter o nome 'INPUT_ExtrusionPlan.xlsx'.");
                    return;
                }

                // Create a FormData object to send the file
                const formData = new FormData();
                formData.append("file", file);

                // Send the file to the API
                const response = await fetch('http://localhost:5001/uploadFile', {
                    method: 'POST',
                    body: formData,
                });

                const responseData = await response.json();
                if (response.ok) {
                    this.criteriaModal({
                        title: "Critérios",
                        criteria: this.criteria,
                        confirmCallback: this.handleModalConfirm,
                    });
                } else {
                    showError(responseData.message);
                }
            } catch (error) {
                console.error("Error:", error);
                showError("Ocorreu um erro. Por favor tente outra vez.");
            }
        },
        handleModalConfirm(selectedCriteria) {
            console.log("Critérios:", selectedCriteria);
            this.criteriaSelected = true;

            fetch("http://localhost:5001/criteria", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify(selectedCriteria),
            })
                .then((response) => response.json())
                .then(() => this.checkIfReadyToFinalize())
                .catch((error) => {
                    alert("Erro no processamento dos critérios. Por favor tente outra vez.");
                });

            this.showCriteriaModal = false;

            if (selectedCriteria[0]) {
                this.fetchMachines();
                this.showRemoveMachinesModal = true;
            }

            if (selectedCriteria[5] && !this.showRemoveMachinesModal) {
                this.fetchBoMs();
                this.showRemoveBoMsModal = true;
            }

            this.selectedCriteria = selectedCriteria;
        },
        async fetchMachines() {
            try {
                const response = await fetch("http://localhost:5001/machines");
                const data = await response.json();
                if (response.ok) {
                    this.availableMachines = data.machines.map(machine => machine.name);
                } else {
                    alert("Erro ao solicitação das máquinas. Por favor tente outra vez.");
                }
            } catch (error) {
                alert("Erro na solicitação das máquinas. Por favor tente outra vez.");
            }
        },
        async fetchBoMs() {
            try {
                const response = await fetch("http://localhost:5001/BoMs");
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
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ machines: selectedMachines }),
            })
                .then((response) => response.json())
                .then(() => this.checkIfReadyToFinalize())
                .catch((error) => {
                    console.error("Erro na solicitação de remoção:", error);
                });

            if (this.selectedCriteria[5]) {
                this.fetchBoMs();
                this.showRemoveBoMsModal = true;
            }
        },
        closeRemoveMachinesModal() {
            this.showRemoveMachinesModal = false;
        },
        handleRemoveBoMsConfirm(selectedBoMs) {
            console.log("BOM's selecionadas para remoção:", selectedBoMs);
            this.showRemoveBoMsModal = false;
            this.bomsRemoved = true;

            fetch("http://localhost:5001/removeBoMs", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ BoMs: selectedBoMs }),
            })
                .then((response) => response.json())
                .then(() => this.checkIfReadyToFinalize())
                .catch((error) => {
                    console.error("Erro na solicitação de remoção:", error);
                });
        },
        closeRemoveBoMsModal() {
            this.showRemoveBoMsModal = false;
        },
        checkIfReadyToFinalize() {
            const isReady =
                this.criteriaSelected &&
                (!this.selectedCriteria[0] || this.machinesRemoved) &&
                (!this.selectedCriteria[5] || this.bomsRemoved);

            if (isReady) {
                fetch('http://localhost:5001/createData', { method: 'POST' })
                    .then(response => response.json())
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
                        fetch('http://localhost:5001/runAlgorithm', { method: 'POST' })
                            .then(response => response.json())
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
            fetch("http://localhost:5001/saveResults", { method: 'POST' })
                .then(response => response.json())
                .then((data) => {
                    console.log("Results saved and new data:", data);
                    this.refreshGanttChart();
                })
                .catch((error) => {
                    console.error("Error saving the results:", error);
                });
        },
        closeResultsModal() {
            this.showResultsModal = false;
        },
        rerunPlan() {
            this.showResultsModal = false;
            this.criteriaModal({
                title: "Critérios",
                criteria: this.criteria,
                confirmCallback: this.handleModalConfirm,
            });
        },
        criteriaModal({ title, criteria, confirmCallback }) {
            this.modalTitle = title;
            this.criteria = criteria;
            this.modalConfirmCallback = confirmCallback;
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

/* Header styling */
.header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    background-color: #4CAF50;
    color: white;
    padding: 10px 20px;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
}

.create-plan-btn {
    padding: 8px 15px;
    background-color: white;
    color: #4CAF50;
    border: none;
    border-radius: 5px;
    cursor: pointer;
    font-size: 16px;
    transition: 0.3s ease;
}

.create-plan-btn:hover {
    background-color: #45a049;
    color: white;
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
