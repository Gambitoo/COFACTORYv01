<template>
    <div class="main-view">
        <header class="header">
            <div ref="detectOutsideClick" class="main-section">
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
            <div v-if="isAdmin" ref="adminSection" class="admin-section" >
                <button @click="toggleAlgorithmMenu" class="terminate-btn">
                    <span>Terminar processamento</span>
                    <font-awesome-icon icon="fa-solid fa-caret-down" class="terminate-dropdown-icon"/>
                </button>
                <div v-if="algorithmMenuOpen" class="dropdown-menu admin-dropdown">
                    <ul v-if="activeUsers.length > 0">
                        <li v-for="userId in activeUsers" :key="userId" @click="abortUserAlgorithm(userId)">
                            <span>{{ userId }}</span>
                        </li>
                    </ul>
                    <ul v-else>
                        <li class="no-users">
                            <span>Nenhum algoritmo ativo</span>
                        </li>
                    </ul>
                </div>
            </div>
            <!--<button @click="createNewPlan" class="create-plan-btn">Criar Novo Plano</button>-->
        </header>

        <div v-if="isAlgorithmRunning" class="loading-tooltip">
            <div class="loading-spinner"></div>
            <p style="margin: 0;">A criar novo plano...</p>
        </div>

        <div v-if="showGanttChart" class="content-container">
            <GanttChart :isLoading="isAlgorithmRunning" :key="renderKey" />
        </div>

        <div v-if="showPlanHistory" class="content-container">
            <PlanHistoryPage @close="closePlanHistoryPage" />
        </div>

        <!-- Other modals -->
        <CriteriaModal v-if="showCriteriaModal" :title="modalTitle" :criteria="criteria" @confirm="handleModalConfirm"
            @close="closeCriteriaModal" />

        <RemoveMachinesModal v-if="showRemoveMachinesModal" :machines="branchMachines[currentBranch]?.machines || []"
            :processes="branchMachines[currentBranch]?.processes || []" @confirm="handleRemoveMachinesConfirm"
            @close="closeRemoveMachinesModal" />

        <RemoveBoMsModal v-if="showRemoveBoMsModal" :BoMs="branchBoMs[currentBranch] || null"
            @confirm="handleRemoveBoMsConfirm" @close="closeRemoveBoMsModal" />

        <!--<ResultsModal v-if="showResultsModal" @confirm="handleResultsConfirm" @cancel="closeResultsModal"
            @rerun="rerunPlan" />-->

        <MissingItemsModal v-if="missingItemsData[userID]?.shouldShow"
            :noRoutings="missingItemsData[userID]?.noRoutings || []" :noBoms="missingItemsData[userID]?.noBoms || []"
            @close="closeMissingItemsModal" />

        <LateOrdersModal v-if="lateOrders[userID]?.shouldShow" :lateOrders="lateOrders[userID]?.orders || []"
            @close="closeLateOrdersModal" />

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
import LateOrdersModal from "@/components/LateOrdersModal.vue";

export default {
    components: { GanttChart, CriteriaModal, RemoveMachinesModal, RemoveBoMsModal, ResultsModal, MissingItemsModal, LateOrdersModal, PlanHistoryPage },
    data() {
        return {
            userID: null as any,
            showCriteriaModal: false,
            showRemoveMachinesModal: false,
            showRemoveBoMsModal: false,
            showGanttChart: false,
            showResultsModal: false,
            showPlanHistory: false,
            modalTitle: "",
            criteria: ["Remover Máquinas", "Organizar por Melhor Cycle Time", "Sequenciamento por Diâmetro", "Consumir Stock disponível", "Menor Número de Mudanças", "Desativar BoMs"],
            selectedCriteria: {},
            selectedFile: null as any,
            currentBranch: null as any,
            branchMachines: {}, // Will store machines by branch
            branchBoMs: {}, // Will store BoMs by branch
            criteriaSelected: false,
            machinesRemoved: false,
            missingItemsData: {},
            lateOrders: {},
            bomsRemoved: false,
            isAlgorithmRunning: false,
            isAdmin: false,
            renderKey: 0,
            menuOpen: false,
            algorithmMenuOpen: false,
            activeUsers: [],
            apiUrl: `http://${import.meta.env.VITE_FLASK_HOST}:${import.meta.env.VITE_FLASK_PORT}`,
        };
    },
    mounted() {
        //window.addEventListener("beforeunload", this.handlePageUnload);
        window.addEventListener("statuscheck", this.pollAlgorithmStatus);
        document.addEventListener('click', this.handleClickOutside);
        //window.addEventListener("admincheck", this.checkAdminPriviliges);
        this.checkUrlParameters();

        // Add resize listener to adjust content height
        window.addEventListener('resize', this.updateContentHeight);
        this.updateContentHeight();

        this.pollAlgorithmStatus();
        this.checkAdminPriviliges();
    },
    beforeDestroy() {
        //window.removeEventListener("beforeunload", this.handlePageUnload);
        window.removeEventListener("statuscheck", this.pollAlgorithmStatus);
        document.removeEventListener('click', this.handleClickOutside);
        window.removeEventListener("admincheck", this.checkAdminPriviliges);
        window.removeEventListener('resize', this.updateContentHeight);
    },
    methods: {
        updateContentHeight() {
            // Calculate and set the minimum height of the content area
            const windowHeight = window.innerHeight;
            const headerHeight = document.querySelector('.header')?.clientHeight || 0;
            const minContentHeight = windowHeight - headerHeight;

            document.documentElement.style.setProperty('--content-min-height', `${minContentHeight}px`);
        },
        handleClickOutside(event) {
            // Check if click is outside the main menu
            if (this.$refs.detectOutsideClick && !this.$refs.detectOutsideClick.contains(event.target)) {
                this.menuOpen = false;
            }
            
            // Check if click is outside the admin menu
            if (this.$refs.adminSection && !this.$refs.adminSection.contains(event.target)) {
                this.algorithmMenuOpen = false;
            }
        },
        // Check and get URL parameters
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

                this.currentBranch = dbBranch;
                this.selectBranchWithParams(dbBranch, userId);
            } else {
                console.error("Branch ou userId missing in URL parameters.");
            }

        },
        toggleMenu() {
            this.menuOpen = !this.menuOpen;
        },
        toggleAlgorithmMenu() {
            this.algorithmMenuOpen = !this.algorithmMenuOpen;
            if (this.algorithmMenuOpen) {
                this.menuOpen = false;
                this.getActiveUsers();
            }
        },
        async getActiveUsers() {
            try {
                const response = await fetch(`${this.apiUrl}/activeAlgorithms?user_id=${this.userID}`, {
                    method: "GET",
                    credentials: 'include',
                    headers: { "Content-Type": "application/json" },
                });

                if (response.ok) {
                    const data = await response.json();
                    this.activeUsers = data.active_users || [];
                } else {
                    console.error(`Erro na obtenção dos utilizadores ativos: ${response.status} ${response.statusText}`);
                    this.activeUsers = [];
                }
            } catch (error) {
                console.error("[activeAlgorithms] Erro na obtenção dos utilizadores ativos:", error);
                this.activeUsers = [];
            }
        },
        openPlanHistoryPage() {
            this.showPlanHistory = true;
            this.menuOpen = false;
            this.showGanttChart = false;
            this.$nextTick(() => this.updateContentHeight());
        },
        closePlanHistoryPage() {
            this.showPlanHistory = false;
            this.showGanttChart = true;
            this.$nextTick(() => this.updateContentHeight());
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
                    this.$nextTick(() => this.updateContentHeight());
                } else {
                    alert(data.message);
                }
            } catch (error) {
                console.error("[selectBranch] Erro no selecionamento da unidade de produção:", error);
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
                console.error("[uploadInputFile] Erro no upload do ficheiro de input:", error);
                alert("Ocorreu um erro. Por favor tente novamente.");
            }
        },
        async handleModalConfirm(selectedCriteria) {
            console.log("Critérios:", selectedCriteria);
            this.criteriaSelected = true;

            try {
                const response = await fetch(`${this.apiUrl}/criteria?user_id=${this.userID}`, {
                    method: "POST",
                    credentials: 'include',
                    headers: {
                        "Content-Type": "application/json",
                    },
                    body: JSON.stringify({ selectedCriteria, allCriteria: this.criteria }),
                })

                if (!response.ok) {
                    alert("Erro no processamento dos critérios. Por favor tente novamente.")
                }
            } catch (error) {
                console.error("[criteria] Erro no processamento dos critérios:", error);
            }

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
                    if (!this.branchMachines[this.currentBranch]) {
                        this.branchMachines[this.currentBranch] = {};
                    }
                    this.branchMachines[this.currentBranch].machines = data.machines.map(machine => machine.name);
                    this.branchMachines[this.currentBranch].processes = data.processes;
                } else {
                    alert("Erro ao solicitação das máquinas. Por favor tente novamente.");
                }
            } catch (error) {
                console.log("[machines] Erro na solicitação das máquinas:", error);
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
                    this.branchBoMs[this.currentBranch] = data.item_BoMs;
                } else {
                    alert("Erro na solicitação das BOM's. Por favor tente novamente.");
                }
            } catch (error) {
                console.log("[BoMs] Erro na obtenção das BOM's:", error);
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
                            if (!this.lateOrders[this.userID]) {
                                this.lateOrders[this.userID] = {
                                    orders: data.late_orders,
                                    shouldShow: true
                                };
                            }

                            //this.showResultsModal = true;
                            //this.handleResultsConfirm();
                        } else if (data.status === 'error') {
                            this.isAlgorithmRunning = false;
                            console.error("Algoritmo falhou:", data.message);
                            alert("Ocorreu um erro na execução do algoritmo. Por favor tente novamente.");
                        } else if (data.status === 'aborted') {
                            this.isAlgorithmRunning = false;
                            console.log("Algoritmo abortado:", data.message);
                            alert("Algoritmo abortado.");
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
                delete this.missingItemsData[this.userID];
            }
        },
        closeLateOrdersModal() {
            if (this.lateOrders[this.userID]) {
                this.lateOrders[this.userID].shouldShow = false;
                delete this.lateOrders[this.userID];
            }
        },
        handleResultsConfirm() {
            this.showResultsModal = false;
            fetch(`${this.apiUrl}/savePlan?user_id=${this.userID}`, {
                method: 'POST',
                credentials: 'include',
            })
                .then(response => {
                    if (!response.ok) {
                        throw new Error("Falha no download dos ficheiros.");
                    }
                    return response.blob();
                })
                .then(blob => {
                    const URL = window.URL.createObjectURL(blob);

                    // Create and configure the anchor element
                    const a = document.createElement('a');
                    a.style.display = 'none';
                    a.href = URL;
                    a.download = 'OUTPUT_Plans.zip'; // File name

                    // Append, click, and cleanup
                    document.body.appendChild(a);
                    a.click();
                    setTimeout(() => {
                        document.body.removeChild(a);
                        window.URL.revokeObjectURL(URL);
                    }, 100);
                })
                .then((data) => {
                    console.log("Resultados guardados com sucesso:", data);
                    this.refreshGanttChart();
                })
                .catch((error) => {
                    console.error("Erro no armazenamento dos resultados:", error);
                    alert("Erro ao guardar o plano gerado. Por favor tente novamente.")
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
        /*async handlePageUnload(event: Event) {
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
        },*/
        abortAlgorithm() {
            if (this.isAlgorithmRunning) {
                try {
                    const url = `${this.apiUrl}/abortAlgorithm`;
                    const data = new Blob([], { type: 'text/plain' });
                    navigator.sendBeacon(url, data);
                } catch (error) {
                    console.error("Erro no envio do sinal de termino do algoritmo:", error);
                }
            }
        },
        async abortUserAlgorithm(userId) {
            try {
                const response = await fetch(`${this.apiUrl}/abortAlgorithm`, {
                    method: 'POST',
                    credentials: 'include',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ user_id: userId }),
                });
                
                if (response.ok) {
                    alert(`Algoritmo do utilizador ${userId} foi terminado.`);
                    // Refresh the active users list
                    this.getActiveUsers();
                } else {
                    const data = await response.json();
                    alert(`Erro ao terminar algoritmo: ${data.message}`);
                }
            } catch (error) {
                console.error("[abortAlgorithm] Erro ao terminar algoritmo:", error);
                alert("Erro ao terminar algoritmo.");
            }
            
            // Close the dropdown
            this.algorithmMenuOpen = false;
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
        async checkAdminPriviliges() {
            try {
                const response = await fetch(`${this.apiUrl}/checkAdminPriviliges?user_id=${this.userID}`, {
                    method: 'GET',
                    credentials: 'include',
                    headers: { "Content-Type": "application/json" },
                });
                
                if (response.ok) {
                    const data = await response.json();
                    if (data.isAdmin == true) {
                        this.isAdmin = true;
                    }
                    else {
                        this.isAdmin = false;
                    }
                }
                else {
                    console.error("Erro na verificação do status do utilizador.");
                    alert("Erro na verificação do status do utilizador.");
                }
            } catch (error) {
                console.log("[checkAdminPriviliges] Erro na verificação do status do utilizador:", error);
                alert("Erro na verificação do status do utilizador.");
            }
        }
    },
};
</script>

<style scoped>
/* Main view layout */
:root {
    --content-min-height: 100vh;
}

html,
body {
    margin: 0;
    padding: 0;
    height: 100%;
}

.main-view {
    display: flex;
    flex-direction: column;
    min-height: 100vh;
}

.content-container {
    flex: 1;
    min-height: var(--content-min-height);
    display: flex;
    flex-direction: column;
}

.header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    background-color: #4CAF50;
    color: white;
    padding: 10px 20px;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    margin-top: 50px;
}

.header h1 {
    margin: 0;
}

.main-section {
    position: relative;
    display: flex;
    align-items: center;
    gap: 15px;
}

.admin-section {
    position: relative;
    display: flex;
    align-items: center;
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

.terminate-btn {
    padding: 8px 15px;
    background-color: #d9534f; /* Red background for terminate action */
    color: white;
    border: none;
    border-radius: 5px;
    cursor: pointer;
    transition: 0.3s ease;
    font-size: 14px;

}

.terminate-btn:hover {
    background-color: #ac433f
}

.terminate-dropdown-icon {
    font-size: 1.2em;
    margin-left: 6px;
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

.admin-dropdown {
    right: 0;
    left: auto;
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

.dropdown-menu li.no-users {
    cursor: default;
    text-align: center;
    color: #666;
}

.dropdown-menu li.no-users:hover {
    background-color: transparent;
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

.loading-tooltip {
    font-weight: bold;
    top: 150px;
    left: 10px;
    position: absolute;
    display: flex;
    align-items: center;
    background: rgba(255, 255, 255, 0.9);
    border: 1px solid #ddd;
    border-radius: 5px;
    padding: 10px 17px;
    box-shadow: 0px 4px 6px rgba(0, 0, 0, 0.1);
}

.loading-spinner {
    border: 3px solid #f3f3f3;
    border-top: 3px solid #3498db;
    border-radius: 50%;
    width: 25px;
    height: 25px;
    animation: spin 1s linear infinite;
    margin-right: 10px;
}

@keyframes spin {
    0% {
        transform: rotate(0deg);
    }

    100% {
        transform: rotate(360deg);
    }
}
</style>