<template>
  <div class="plan-history">
    <h2>Histórico de Planos</h2>
    <table>
      <thead>
        <tr>
        <th>Utilizador</th>
          <th>
            Tempo de Início 
            <button @click="sortBy('ST')" :class="'sort'">
              <font-awesome-icon icon="sort" />
            </button>
          </th>
          <th>
            Tempo de Conclusão 
            <button @click="sortBy('CoT')" :class="'sort'">
              <font-awesome-icon icon="sort" />
            </button>
          </th>
          <th>Critérios</th>
          <th>Ficheiro Input</th>
          <th>Ficheiros Output</th>
          <th>Plano</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(plan, index) in plans" :key="index">
          <td>{{ plan.user_id }}</td>
          <td>{{ formatDate(plan.ST) }}</td>
          <td>{{ formatDate(plan.CoT) }}</td>
          <td>{{ plan.criteria.join() }}</td> 
          <td>
            <div class="button-container">
              <button v-for="(file, idx) in plan.inputFiles" :key="idx" @click="downloadFile(file)">
                Download
              </button>
            </div>
          </td>
          <td>
            <div class="button-container">
              <button v-for="(file, idx) in plan.outputFiles" :key="idx" @click="downloadFile(file)">
                Download
              </button>
            </div>
          </td>
          <td>
            <div class="button-container">
              <button @click="openGanttModal(plan)">
                Ver Plano
              </button>
            </div>
          </td>
        </tr>
      </tbody>
    </table>
    <button class="close-btn" @click="$emit('close')">Fechar</button>

    <div v-if="showGanttModal" class="gantt-modal">
      <div class="modal-container">
        <div class="modal-header">
          <h3>Visualização do Plano</h3>
          <button @click="closeGanttModal" class="gantt-close-btn">×</button>
        </div>
        <div class="modal-content">
          <ResultsGanttChart 
            :uniqueId="`${formatDateForId(formatDate(selectedPlan.ST))}_${selectedPlan.user_id}`" 
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
import ResultsGanttChart from "@/components/ResultsGanttChart.vue";

export default {
  components: { ResultsGanttChart },
  data() {
    return {
      plans: [] as any[], // Store historical plans
      currentSortOrder: {
        ST: 'asc', // Default sort order for 'Tempo de Início'
        CoT: 'asc', // Default sort order for 'Tempo de Conclusão'
      },
      showGanttModal: false,
      selectedPlan: null,
      apiUrl: import.meta.env.VITE_FLASK_HOST 
                ? `http://${import.meta.env.VITE_FLASK_HOST}:${import.meta.env.VITE_FLASK_PORT}`
                : 'http://localhost:5001',
    };
  },
  async mounted() {
    await this.fetchPlanHistory();
  },
  methods: {
    async fetchPlanHistory() {
      try {
        const response = await fetch(`${this.apiUrl}/getPlanHistory`, {
          method: "POST",
          credentials: "include",
        });
        if (response.ok) {
          this.plans = await response.json();
        } else {
          alert("Erro ao obter histórico de planos.");
        }
      } catch (error) {
        console.error("Erro ao carregar o histórico:", error);
      }
    },
    formatDate(timestamp: number | string) {
      // Format for display
      return timestamp ? new Date(timestamp).toLocaleString("pt-PT") : "N/A";
    },
    formatDateForId(timestamp) {
      // Format date for userId concatenation
      if (!timestamp) return '';

      const date = new Date(timestamp);

      // Format as DDMMYYYYHHmmss
      const day = String(date.getDate());
      const month = String(date.getMonth() + 1).padStart(2, '0');
      const year = date.getFullYear();
      const hours = String(date.getHours()).padStart(2, '0');
      const minutes = String(date.getMinutes()).padStart(2, '0');
      const seconds = String(date.getSeconds()).padStart(2, '0');

      return `${day}${month}${year}${hours}${minutes}${seconds}`;
    },
    downloadFile(url: string) {
      const link = document.createElement("a");
      link.href = url;
      link.download = url.split("/").pop() || "file";
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    },
    sortBy(column: string) {
      this.currentSortOrder[column] = this.currentSortOrder[column] === 'asc' ? 'desc' : 'asc';
      
      this.plans.sort((a, b) => {
        const aVal = a[column];
        const bVal = b[column];

        if (this.currentSortOrder[column] === 'asc') {
          return new Date(aVal).getTime() - new Date(bVal).getTime();
        } else {
          return new Date(bVal).getTime() - new Date(aVal).getTime();
        }
      });
    },
    openGanttModal(plan) {
      this.selectedPlan = plan;
      this.showGanttModal = true;
    },
    closeGanttModal() {
      this.showGanttModal = false;
      this.selectedPlan = null;
    }
  },
};
</script>

<style scoped>
.plan-history {
  padding: 20px;
  background: white;
  border-radius: 10px;
  box-shadow: 0px 4px 6px rgba(0, 0, 0, 0.1);
}

table {
  width: 100%;
  border-collapse: collapse;
}

th, td {
  padding: 10px;
  border-bottom: 1px solid #ddd;
  border-top: 1px solid #ddd;
}

th {
  background-color: #f4f4f4;
}

button {
  padding: 5px 10px;
  border: none;
  background: #4CAF50;
  color: white;
  cursor: pointer;
}

.button-container {
  display: flex;
  justify-content: center; /* Center buttons horizontally */
  align-items: center;
}

button:hover {
  background: #45a049;
}

.close-btn {
  margin-top: 15px;
  background: #d9534f;
}

button.sort {
  all: unset; 
  color: black;
  margin-left: 5px;
}

.sort:hover {
  color: gray;
}

.gantt-modal {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  justify-content: center;
  align-items: center;
}

.modal-container {
  background: #fff;
  border-radius: 10px;
  width: 90%;
  max-height: 90vh;
  overflow: auto;
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 15px 20px;
  border-bottom: 1px solid #eee;
}

.modal-content {
  padding: 10px;
}

.gantt-close-btn {
  background: #d9534f;
}
</style>
