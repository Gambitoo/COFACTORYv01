<template>
  <div class="modal-backdrop">
    <div class="modal-content">
      <!-- Warning symbol and title -->
      <div class="warning-header">
        <span class="warning-symbol">⚠️</span>
        <h2>Aviso</h2>
        <span class="warning-symbol">⚠️</span>
      </div>

      <!-- Items without Routing -->
      <div v-if="noRoutings && noRoutings.length > 0">
        <h3>Itens sem Routing</h3>
        <ul>
          <li v-for="item in noRoutings" :key="item">{{ item }}</li>
        </ul>
      </div>

      <!-- Items without BoM's -->
      <div v-if="noBoms && noBoms.length > 0">
        <h3>Itens sem BOM:</h3>
        <ul>
          <li v-for="item in noBoms" :key="item">{{ item }}</li>
        </ul>
      </div>

      <div class="modal-actions">
        <button @click="close">Fechar</button>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
export default {
  props: {
    noRoutings: Array,
    noBoms: Array,
  },
  methods: {
    close() {
      this.$emit('close');
    }
  },
};
</script>

<style scoped>
.modal-backdrop {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 999; 
}

.modal-content {
  background: #ffffff;
  padding: 20px;
  border-radius: 10px;
  box-shadow: 0px 4px 12px rgba(0, 0, 0, 0.2);
  max-width: 600px;
  width: 90%; 
  overflow-y: auto;
  z-index: 1000;
}

.warning-header {
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 20px;
  color: #f39c12; 
}

.warning-symbol {
  font-size: 1.5rem;
  margin-right: 10px;
  margin-left: 10px;
}

.modal-content h2 {
  font-size: 1.5rem;
  color: #333;
  font-weight: bold;
}

h3 {
  font-size: 1.2rem;
  margin-top: 15px;
  color: #2c3e50;
  font-weight: bold;
}

.modal-content ul {
  list-style-type: none;
  padding-left: 0;
  margin: 0;
}

.modal-content li {
  padding: 8px;
  background-color: #f9f9f9;
  border: 1px solid #ddd;
  margin-bottom: 5px;
  border-radius: 5px;
  color: #333;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 20px;
}

.modal-actions button {
  padding: 10px 20px;
  background-color: #4CAF50;
  color: white;
  border: none;
  border-radius: 5px;
  cursor: pointer;
  font-size: 1rem;
  transition: background-color 0.3s ease;
}

.modal-actions button:hover {
  background-color: #45a049;
}
</style>
