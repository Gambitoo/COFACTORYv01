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
</template>

<script lang="ts">
import GanttChart from "@/components/GanttChart.vue";
import CriteriaModal from "@/components/CriteriaModal.vue";
import RemoveMachinesModal from "@/components/RemoveMachinesModal.vue";
import RemoveBoMsModal from "@/components/RemoveBoMsModal.vue";
import ResultsModal from "@/components/ResultsModal.vue";
import MissingItemsModal from "@/components/MissingItemsModal.vue";
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
    async mounted() {
        await this.checkUrlParameters();

        // Add event listener to check for algorithm status
        window.addEventListener("statuscheck", this.pollAlgorithmStatus);
        document.addEventListener('click', this.handleClickOutside);
        //window.addEventListener("admincheck", this.checkAdminPriviliges);

        // Add resize listener to adjust content height
        window.addEventListener('resize', this.updateContentHeight);
        this.updateContentHeight();

        this.checkAdminPrivileges();
        this.pollAlgorithmStatus();
    },
    beforeDestroy() {
        window.removeEventListener("statuscheck", this.pollAlgorithmStatus);
        document.removeEventListener('click', this.handleClickOutside);
        window.removeEventListener("admincheck", this.checkAdminPrivileges);
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
        async checkUrlParameters() {
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
                await this.selectBranchWithParams(dbBranch, userId);
            } else {
                alert("Erro: Parâmetros em falta no URL");
                console.error("[checkUrlParameters] Error: Branch or User ID missing from the URL parameters.");
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
                
                const data = await this.handleResponse(response, "activeAlgorithms");
                this.activeUsers = data.active_users || [];
                
            } catch (error) {
                alert(error.message);
                console.error("[activeAlgorithms] Error:", error.message);
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
                const response = await fetch(`${this.apiUrl}/selectBranch?user_id=${userId}`, {
                    method: 'POST',
                    credentials: 'include',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ branch, userId }),
                });
            
                await this.handleResponse(response, "selectBranch");

                this.userID = userId;
                this.showBranchModal = false;
                this.showGanttChart = true;
                this.$nextTick(() => this.updateContentHeight());
            
            } catch (error) {
                alert(error.message || "Erro no selecionamento da unidade de produção. Por favor tente novamente.");
                console.error("[selectBranch] Error:", error.message);
            }
        },
        async createNewPlan() {
            this.menuOpen = false;

            try {
                const file = await this.openFilePicker();
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
                });
            
                await this.handleResponse(response, "uploadInputFile");

                this.criteriaModal({
                    title: "Critérios",
                    criteria: this.criteria,
                });
            
            } catch (error) {
                console.error("[uploadInputFile] Error:", error.message);
                alert(error.message || "Ocorreu um erro no upload do ficheiro. Por favor tente novamente.");
            }
        },
        async openFilePicker() {
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
                console.error("[openFilePicker] Error:", error.message);
                return null; 
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
                });
            
                await this.handleResponse(response, "criteria");

                // Success - continue with workflow
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
            
            } catch (error) {
                console.error("[criteria] Error:", error.message);
                alert(error.message || "Erro no processamento dos critérios. Por favor tente novamente.");

                // Reset state on error
                this.criteriaSelected = false;
                this.showCriteriaModal = false;
            }
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
            
                const data = await this.handleResponse(response, "machines");

                if (!this.branchMachines[this.currentBranch]) {
                    this.branchMachines[this.currentBranch] = {};
                }
                this.branchMachines[this.currentBranch].machines = data.machines.map(machine => machine.name);
                this.branchMachines[this.currentBranch].processes = data.processes;
            
            } catch (error) {
                console.error("[machines] Error:", error.message);
                alert(error.message || "Erro na solicitação das máquinas. Por favor tente novamente.");
            }
        },
        async fetchBoMs() {
            try {
                const response = await fetch(`${this.apiUrl}/BoMs`, {
                    method: 'GET',
                    credentials: 'include',
                });
            
                const data = await this.handleResponse(response, "BoMs");

                this.branchBoMs[this.currentBranch] = data.item_BoMs;
            
            } catch (error) {
                console.error("[BoMs] Error:", error.message);
                alert(error.message || "Erro na solicitação das BOMs. Por favor tente novamente.");
            }
        },
        async handleRemoveMachinesConfirm(selectedMachines) {
            console.log("Máquinas selecionadas para remoção:", selectedMachines);
            this.showRemoveMachinesModal = false;
            this.machinesRemoved = true;
        
            try {
                const response = await fetch(`${this.apiUrl}/removeMachines?user_id=${this.userID}`, {
                    method: "POST",
                    credentials: 'include',
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(selectedMachines),
                });
            
                await this.handleResponse(response, "removeMachines");

                if (this.selectedCriteria[5]) {
                    await this.fetchBoMs();
                    this.showRemoveBoMsModal = true;
                } else {
                    this.checkIfReadyToFinalize();
                }
            
            } catch (error) {
                console.error("[removeMachines] Error:", error.message);
                alert(error.message || "Erro na remoção das máquinas. Por favor tente novamente.");

                this.showRemoveMachinesModal = true;
                this.machinesRemoved = false;
            }
        },
        closeRemoveMachinesModal() {
            this.deleteFileRequest();
            this.showRemoveMachinesModal = false;
        },
        async handleRemoveBoMsConfirm(selectedBoMs) {
            console.log("BOMs selecionadas para remoção:", selectedBoMs);
            this.showRemoveBoMsModal = false;
            this.bomsRemoved = true;
        
            try {
                const response = await fetch(`${this.apiUrl}/removeBoMs?user_id=${this.userID}`, {
                    method: "POST",
                    credentials: 'include',
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(selectedBoMs),
                });
            
                await this.handleResponse(response, "removeBoMs");

                this.checkIfReadyToFinalize();
            
            } catch (error) {
                console.error("[removeBoMs] Error:", error.message);
                alert(error.message || "Erro na remoção das BOMs. Por favor tente novamente.");

                this.showRemoveBoMsModal = true;
                this.bomsRemoved = false;
            }
        },
        closeRemoveBoMsModal() {
            this.deleteFileRequest();
            this.showRemoveBoMsModal = false;
        },
        async checkIfReadyToFinalize() {
            const isReady =
                this.criteriaSelected &&
                (!this.selectedCriteria[0] || this.machinesRemoved) &&
                (!this.selectedCriteria[5] || this.bomsRemoved);
        
            if (!isReady) return;
        
            try {
                // Create data and check for missing items
                const createResponse = await fetch(`${this.apiUrl}/createData?user_id=${this.userID}`, {
                    method: 'POST',
                    credentials: 'include',
                });
            
                const data = this.handleResponse(createResponse, "createData");
           
                // Initialize missing items data
                if (!this.missingItemsData[this.userID]) {
                    this.missingItemsData[this.userID] = {
                        noRoutings: [],
                        noBoms: [],
                        shouldShow: false
                    };
                }
            
                // Update missing items
                if (data.no_routings?.length > 0) {
                    this.missingItemsData[this.userID].noRoutings = data.no_routings;
                }
            
                if (data.no_bom?.length > 0) {
                    this.missingItemsData[this.userID].noBoms = data.no_bom;
                }
            
                // Show modal if there are missing items
                if (this.missingItemsData[this.userID].noRoutings.length > 0 ||
                    this.missingItemsData[this.userID].noBoms.length > 0) {
                    this.missingItemsData[this.userID].shouldShow = true;
                }
            
                // Start algorithm
                this.isAlgorithmRunning = true;
            
                const algorithmResponse = await fetch(`${this.apiUrl}/runAlgorithm?user_id=${this.userID}`, {
                    method: 'POST',
                    credentials: 'include',
                });
            
                await this.handleResponse(algorithmResponse, "runAlgorithm");
            
                // Start polling for status
                this.pollAlgorithmStatus();
            
            } catch (error) {
                console.error("[checkIfReadyToFinalize] Error:", error.message);

                this.isAlgorithmRunning = false;

                alert(error.message || "Ocorreu um erro inesperado. Por favor tente novamente.");
            }
        },
        pollAlgorithmStatus() {
            if (!this.userID) {
                console.warn("[pollAlgorithmStatus] Cannot poll algorithm status: userID not available.");
                return;
            }    

            let consecutiveErrors = 0;
            const maxConsecutiveErrors = 3;

            const checkStatus = async () => {
                try {
                    const response = await fetch(`${this.apiUrl}/algorithmStatus?user_id=${this.userID}`, {
                        credentials: 'include',
                    });

                    consecutiveErrors = 0;

                    if (!response.ok) {
                        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                    }

                    const data = await response.json();
                    switch(data.status) {
                        case 'completed':
                            this.isAlgorithmRunning = false;
                            if (!this.lateOrders[this.userID]) {
                                this.lateOrders[this.userID] = {
                                    orders: data.late_orders,
                                    shouldShow: true
                                };
                            }
                            break;
                        case 'error':
                            this.isAlgorithmRunning = false;
                            console.error("[algorithmStatus] Error:", data.message);
                            alert(data.message || "Erro na execução do algoritmo.");
                            break;
                        case 'aborted':
                            this.isAlgorithmRunning = false;
                            console.error("[algorithmStatus] Error:", data.message);
                            alert(data.message || "Algoritmo foi abortado.");
                            break;
                        case 'not_running':
                            this.isAlgorithmRunning = false;
                            break;
                        case 'running':
                            // Still running, check again in 2 seconds
                            setTimeout(checkStatus, 2000);
                            break;
                        default:
                            // Still running, check again in 2 seconds
                            this.isAlgorithmRunning = true;
                            setTimeout(checkStatus, 2000);
                            break;
                    }
                } catch (error) {
                    console.error("[algorithmStatus] Error:", data.message);
    
                    if (consecutiveErrors >= maxConsecutiveErrors) {
                        // Stop polling after too many consecutive errors
                        this.isAlgorithmRunning = false;
                        alert(error.message || "Não foi possível verificar o estado do algoritmo. Por favor atualize a página.");
                        return;
                    }

                    if (this.isAlgorithmRunning) {
                        // Longer delays after errors
                        const delay = Math.min(5000 * Math.pow(2, consecutiveErrors - 1), 30000);
                        setTimeout(checkStatus, delay);
                    }
                }
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
        async handleResultsConfirm() {
            this.showResultsModal = false;
            try {
                const response = await fetch(`${this.apiUrl}/savePlan?user_id=${this.userID}`, {
                    method: 'POST',
                    credentials: 'include',
                });
            
                const fileResponse = await this.handleResponse(response, "savePlan");
            
                const blob = await fileResponse.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');

                a.style.display = 'none';
                a.href = url;
                a.download = filename;

                document.body.appendChild(a);
                a.click();

                // Cleanup
                setTimeout(() => {
                    document.body.removeChild(a);
                    window.URL.revokeObjectURL(url);
                }, 100);

                console.log("[savePlan] Results successfully saved.");
                this.refreshGanttChart();
            
            } catch (error) {
                console.error("[savePlan] Error:", error);
                alert(error.message || "Erro ao guardar o plano gerado. Por favor tente novamente.");
            }
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
                    console.error("[abortAlgorithm] Error:", error.message);

                    // Fallback request
                    this.fallbackAbortRequest();
                }
            }
        },
        fallbackAbortRequest() {
            fetch(`${this.apiUrl}/abortAlgorithm`, {
                method: 'POST',
                credentials: 'include',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: this.userID }),
                keepalive: true 
            }).catch(error => {
                console.error("[abortAlgorithm] Fallback error:", error.message);
            });
        },
        async abortUserAlgorithm(userId) {
            try {
                const response = await fetch(`${this.apiUrl}/abortAlgorithm`, {
                    method: 'POST',
                    credentials: 'include',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ user_id: userId }),
                });

                await this.handleResponse(response, "abortAlgorithm");

                alert(`Algoritmo do utilizador ${userId} foi terminado.`);
                // Refresh active users list
                this.getActiveUsers();
            } catch (error) {
                console.log("[abortAlgorithm] Error:", error.message)
                let userMessage = "Erro ao terminar algoritmo.";

                if (error.message.includes('404')) {
                    userMessage = `Nenhum algoritmo ativo encontrado para o utilizador ${userId}.`;
                } else if (error.message.includes('403')) {
                    userMessage = "Não tem permissão para terminar algoritmos de outros utilizadores.";
                } else if (error.message.includes('500')) {
                    userMessage = "Erro no servidor. Por favor tente novamente.";
                }

                alert(userMessage);
            } finally {
                // Always close the dropdown
                this.algorithmMenuOpen = false;
            }
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
                    console.warn("[deleteInputFile] Warning:", error.message);
                });
        },
        async checkAdminPrivileges() {
            if (!this.userID) return;

            try {
                const response = await fetch(`${this.apiUrl}/checkAdminPrivileges?user_id=${this.userID}`, {
                    method: 'GET',
                    credentials: 'include',
                });

                const data = await this.handleResponse(response, "checkAdminPrivileges");

                // Update admin status
                this.isAdmin = Boolean(data.isAdmin);

            } catch (error) {
                console.warn("[checkAdminPrivileges] Warning:", error.message);
                this.isAdmin = false; // Safe default
            }
        },
        async handleResponse(response, context) {
            // Check status first
            if (!response.ok) {
                // Try to get detailed error message
                const contentType = response.headers.get('content-type');

                if (contentType?.includes('application/json')) {
                    try {
                        const errorData = await response.json();
                        console.log(`[${context}] Error: ${errorData.message || response.statusText}`)
                        throw new Error(errorData.message || response.statusText);
                    } catch {
                        console.log(`[${context}] Error: ${response.statusText}`)
                        throw new Error(response.statusText);
                    }
                } else {
                    // Not JSON, so use status text
                    console.log(`[${context}] Error: ${response.statusText}`)
                    throw new Error(response.statusText);
                }
            }

            // Only parse successful responses
            const contentType = response.headers.get('content-type');
    
            if (contentType?.includes('application/json')) {
                return await response.json();
            } else if (contentType?.includes('text/')) {
                return await response.text();
            } else {
                // For blobs, files, etc.
                return response;
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
    background-color: #d9534f;
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