<template>
  <div class="gantt-modal">
    <div class="modal-container">
      <div class="modal-header">
        <h2>Novo Planeamento</h2>
        <button @click="cancel" class="cancel-btn">
          <font-awesome-icon icon="xmark" />
        </button>
      </div>
      <div class="modal-content">
        <!-- Render the Gantt chart -->
        <ResultsGanttChart/>
      </div>
      <div class="button-group">
        <button @click="confirm" class="confirm-btn">Guardar</button>
        <button @click="rerun" class="rerun-btn">Correr Novamente</button>
        
      </div>
    </div>
  </div>
</template>

<script lang="ts">
import ResultsGanttChart from "@/components/ResultsGanttChart.vue";
import { FontAwesomeIcon } from '@fortawesome/vue-fontawesome';

export default {
  components: { ResultsGanttChart, FontAwesomeIcon },
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

.button-group {
  display: flex;
  justify-content: space-between;
  margin-top: 20px;
  padding: 15px 15px;
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

.cancel-btn {
  background-color: #f44336;
  color: white;
  border: none;
  border-radius: 5px;
  cursor: pointer;
  transition: 0.3s;
  padding: 5px 10px;
}

.cancel-btn:hover {
  background: #45a049;
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
