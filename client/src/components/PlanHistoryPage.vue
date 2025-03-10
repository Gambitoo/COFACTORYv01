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
              <button>
                <ResultsGanttChart :data="chartData" :uniqueId="`${formatDateForId(formatDate(plan.ST))}_${plan.user_id}`" />
              </button>
            </div>
          </td>
        </tr>
      </tbody>
    </table>
    <button class="close-btn" @click="$emit('close')">Fechar</button>
  </div>
</template>

<script lang="ts">
import ResultsGanttChart from "@/components/ResultsGanttChart.vue";

export default {
  components: { ResultsGanttChart },
  props: {
    chartData: {
      type: Array,
      required: true,
    },
  },
  data() {
    return {
      plans: [] as any[], // Store historical plans
      currentSortOrder: {
        ST: 'asc', // Default sort order for 'Tempo de Início'
        CoT: 'asc', // Default sort order for 'Tempo de Conclusão'
      },
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
      return timestamp ? new Date(timestamp).toLocaleString(pt-PT) : "N/A";
    },
    formatSTForId(timestamp) {
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
</style>
