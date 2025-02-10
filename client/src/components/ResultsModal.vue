<template>
  <div class="gantt-modal">
    <div class="modal-content">
      <h2>Novo Planeamento</h2>
      <div class="gantt-chart">
        <!-- Render the Gantt chart -->
        <ResultsGanttChart :data="chartData" />
      </div>
      <div class="button-group">
        <button @click="confirm" class="confirm-btn">Guardar</button>
        <button @click="rerun" class="rerun-btn">Correr Novamente</button>
        <button @click="cancel" class="cancel-btn">Cancelar</button>
      </div>
    </div>
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
  methods: {
    confirm() {
      this.$emit("confirm");
    },
    cancel() {
      if (confirm("Tem a certeza que deseja descartar este plano?"))
      this.$emit("cancel");
    },
    rerun() {
      this.$emit("rerun");
    },
  },
};
</script>

<style scoped>
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

.modal-content {
  background: #fff;
  padding: 20px;
  border-radius: 10px;
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
  width: 90%;
  max-height: 95%;
  overflow-y: auto;
}

.button-group {
  display: flex;
  justify-content: space-between;
  margin-top: 20px;
}

.button-group .confirm-btn {
  padding: 10px 20px;
  background-color: #4caf50;
  color: white;
  border: none;
  border-radius: 5px;
  cursor: pointer;
  transition: 0.3s;
}

.button-group .confirm-btn:hover {
  background-color: #45a049;
}

.button-group .cancel-btn {
  padding: 10px 20px;
  background-color: #f44336;
  color: white;
  border: none;
  border-radius: 5px;
  cursor: pointer;
  transition: 0.3s;
}

.button-group .cancel-btn:hover {
  background-color: #d32f2f;
}

.button-group .rerun-btn {
  padding: 10px 20px;
  background-color: #2196f3; 
  color: white;
  border: none;
  border-radius: 5px;
  cursor: pointer;
  transition: 0.3s;
}

.button-group .rerun-btn:hover {
  background-color: #1976d2;
}
</style>
