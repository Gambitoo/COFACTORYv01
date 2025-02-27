<template>
    <div class="plan-history">
      <h2>Histórico de Planos</h2>
      <table>
        <thead>
          <tr>
            <th>Utilizador</th>
            <th>Tempo de Início</th>
            <th>Tempo de Conclusão</th>
            <th>Ficheiro Input</th>
            <th>Ficheiros Output </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="plan in plans" :key="plan.id">
            <td>{{ plan.userId }}</td>
            <td>{{ formatDate(plan.startingTime) }}</td>
            <td>{{ formatDate(plan.completionTime) }}</td>
            <td>
              <button @click="downloadFile(plan.inputFileUrl)">Download</button>
            </td>
            <td>
              <button @click="downloadFile(plan.outputZipUrl)">Download</button>
            </td>
          </tr>
        </tbody>
      </table>
      <button class="close-btn" @click="$emit('close')">Fechar</button>
    </div>
  </template>
  
  <script lang="ts">
  export default {
    data() {
      return {
        plans: [] as any[], // Historical plan records
      };
    },
    async mounted() {
      await this.fetchPlanHistory();
    },
    methods: {
      async fetchPlanHistory() {
        try {
          const response = await fetch("http://localhost:5001/getPlanHistory", {
            method: "POST",
            credentials: "include",
          });
          /*if (response.ok) {
            this.plans = await response.json();
          } else {
            alert("Erro ao obter histórico de planos.");
          }*/
        } catch (error) {
          console.error("Erro ao carregar o histórico:", error);
        }
      },
      formatDate(timestamp: string) {
        return new Date(timestamp).toLocaleString();
      },
      downloadFile(url: string) {
        const link = document.createElement("a");
        link.href = url;
        link.download = url.split("/").pop() || "file";
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
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
    text-align: left;
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
  
  button:hover {
    background: #45a049;
  }
  
  .close-btn {
    margin-top: 10px;
    background: #d9534f;
  }
  </style>
  