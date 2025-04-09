<template>
  <div class="modal-backdrop">
    <div class="modal-content">
      <!-- Warning symbol and title -->
      <div class="warning-header">
        <span class="warning-symbol">⚠️</span>
        <h2>Aviso</h2>
        <span class="warning-symbol">⚠️</span>
      </div>

      <!-- Late Items -->
      <div v-if="lateOrders && lateOrders.length > 0" class="late-orders-section">
        <h3>Produtos Atrasados</h3>
        <ul class="late-orders-list">
          <li v-for="item in lateOrders" :key="item" class="late-order-item">
            <span class="late-order-name">{{ item }}</span>
          </li>
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
    lateOrders: Array,
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
  font-size: 1.3rem;
  margin-bottom: 15px;
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
  border-bottom: 2px solid #eee;
  margin-bottom: 3px;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 15px;
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

.late-orders-section {
  margin-bottom: 15px;
}

.late-orders-list {
  list-style-type: none;
  padding: 0;
  max-height: 400px;
  overflow-y: auto;
  border: 1px solid #ccc;
  border-radius: 4px;
}

.late-order-item {
  padding: 10px 15px;
  display: flex;
  align-items: center;
}

.late-order-item:last-child {
  border-bottom: none;
}

.late-order-item:hover {
  background-color: #f9f9f9;
}

.late-order-name {
  font-size: 15px;
  color: #333;
}
</style>
