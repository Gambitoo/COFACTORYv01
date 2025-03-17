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
        <tr v-for="(plan, index) in paginatedPlans" :key="index">
          <td>{{ plan.user_id }}</td>
          <td>{{ formatDate(plan.ST) }}</td>
          <td>{{ formatDate(plan.CoT) }}</td>
          <td>
            <div class="button-container">
              <button @click="openCriteriaModal(plan.criteria)">
                Ver Critérios
              </button>
            </div>
          </td>
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

    <!-- Pagination controls -->
    <div class="pagination">
      <button @click="changePage(currentPage - 1)" :disabled="currentPage === 1" class="page-button">
        <font-awesome-icon icon="arrow-left" />
      </button>
      <span class="page-info">
        Página {{ currentPage }} de {{ totalPages }}
      </span>
      <button @click="changePage(currentPage + 1)" :disabled="currentPage === totalPages" class="page-button">
        <font-awesome-icon icon="arrow-right" />
      </button>
    </div>

    <button class="close-btn" @click="$emit('close')">Fechar</button>

    <div v-if="showCriteriaModal" class="modal">
      <div class="criteria-container">
        <div class="criteria-header">
          <h3>Critérios</h3>
          <button @click="closeCriteriaModal" class="modal-close-btn">
            <font-awesome-icon icon="xmark" />
          </button>
        </div>
        <div class="modal-content">
          <ul class="criteria-list">
            <li v-for="(option, index) in processCriteria(this.criteria)" :key="index" class="criteria-item">
              <span class="criteria-name">{{ option.name }}</span>

              <!-- Display list values if they exist -->
              <div v-if="option.valueType === 'list'" class="criteria-values">
                <ul>
                  <li v-for="(value, valueIndex) in option.values" :key="valueIndex">
                    {{ value }}
                  </li>
                </ul>
              </div>

              <div v-if="option.valueType === 'dict'" class="criteria-values">
                <div v-for="(entry, index) in option.values" :key="index" class="bom-group">
                  <h3>{{ entry.rootItem }}</h3>
                  <ul>
                    <li v-for="(bomItem, idx) in entry.bomItems" :key="idx">
                      {{ bomItem }}
                    </li>
                  </ul>
                </div>
              </div>
            </li>
          </ul>
        </div>
      </div>
    </div>

    <div v-if="showGanttModal" class="modal">
      <div class="gantt-container">
        <div class="gantt-header">
          <h3>Visualização do Plano</h3>
          <button @click="closeGanttModal" class="modal-close-btn">
            <font-awesome-icon icon="xmark" />
          </button>
        </div>
        <div class="modal-content">
          <ResultsGanttChart :planoId="`${formatDateForId(formatDate(selectedPlan.ST))}_${selectedPlan.user_id}`" />
        </div>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
import ResultsGanttChart from "@/components/ResultsGanttChart.vue";
import { FontAwesomeIcon } from '@fortawesome/vue-fontawesome';

export default {
  components: { ResultsGanttChart, FontAwesomeIcon },
  data() {
    return {
      plans: [] as any[], // Store historical plans
      currentSortOrder: {
        ST: 'asc', // Default sort order for 'Tempo de Início'
        CoT: 'asc', // Default sort order for 'Tempo de Conclusão'
      },
      showGanttModal: false,
      showCriteriaModal: false,
      selectedPlan: null,
      criteria: null,
      apiUrl: `${import.meta.env.VITE_FLASK_HOST}:${import.meta.env.VITE_FLASK_PORT}`,
      currentPage: 1,
      itemsPerPage: 10,
    };
  },
  computed: {
    totalPages() {
      return Math.ceil(this.plans.length / this.itemsPerPage);
    },
    paginatedPlans() {
      const startIndex = (this.currentPage - 1) * this.itemsPerPage;
      const endIndex = startIndex + this.itemsPerPage;
      return this.plans.slice(startIndex, endIndex);
    }
  },
  async mounted() {
    await this.fetchPlanHistory();
  },
  methods: {
    totalPages() {
      return Math.ceil(this.plans.length / this.itemsPerPage);
    },
    paginatedPlans() {
      const startIndex = (this.currentPage - 1) * this.itemsPerPage;
      const endIndex = startIndex + this.itemsPerPage;
      return this.plans.slice(startIndex, endIndex);
    },
    async fetchPlanHistory() {
      try {
        const response = await fetch(`${this.apiUrl}/getPlanHistory`, {
          method: "POST",
          credentials: "include",
        });
        if (response.ok) {
          this.plans = await response.json();
          // Reset to first page whenever data changes
          this.currentPage = 1;
        } else {
          alert("Erro ao obter histórico de planos.");
        }
      } catch (error) {
        console.error("Erro ao carregar o histórico:", error);
      }
    },
    changePage(page) {
      if (page >= 1 && page <= this.totalPages) {
        this.currentPage = page;
        // Scroll to top of table when changing pages
        this.$el.querySelector('table').scrollIntoView({ behavior: 'smooth' });
      }
    },
    formatDate(timestamp: number | string) {
      // Format for display
      return timestamp ? new Date(timestamp).toLocaleString("pt-PT") : "N/A";
    },
    formatDateForId(timestamp) {
      const [datePart, timePart] = timestamp.split(', ');
      const [day, month, year] = datePart.split('/');
      const [hours, minutes, seconds] = timePart.split(':');

      // Return the formatted string directly
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

      // Reset to first page after sorting
      this.currentPage = 1;
    },
    processCriteria(criteriaArray) {
      return criteriaArray.map(criterion => {
        criterion = criterion.trim();

        // Check if this criterion has additional values (contains a colon)
        if (criterion.includes(':')) {
          // Find the position of the first colon that separates the name from values
          const colonIndex = criterion.indexOf(':');
          const name = criterion.substring(0, colonIndex).trim();

          // Get everything after the first colon as the values string
          let valuesString = criterion.substring(colonIndex + 1).trim();

          if (valuesString.startsWith('[')) {
            // This is a complex structure (array or object)
            return {
              name: name.trim().replace(/,/g, ''),
              valueType: 'list',
              values: this.formatComplexValue(valuesString)
            };
          } else {
            return {
              name: name.trim().replace(/,/g, ''),
              valueType: 'dict',
              values: this.formatComplexValue(valuesString)
            };
          }
        } else {
          // Simple criterion with no additional values
          return {
            name: criterion.trim().replace(/,/g, ''),
            valueType: 'none',
            values: null
          };
        }
      });
    },
    formatComplexValue(valueStr) {
      if (valueStr.startsWith('[')) {

        const content = valueStr.substring(1, valueStr.length - 1);

        // Extract items between square brackets and split by commas
        const items = content
          .replace(/^\[|\]$/g, '') // Remove outer brackets
          .split(',')
          .map(item => item.trim().replace(/[^a-zA-Z0-9]/g, '')); // Remove quotes

        return items;
      }

      // For dictionaries like {'B0037X02840S050CU': [['D07X02840CU', 'D10X02840CU']]}
      if (valueStr.startsWith('{')) {
        try {
          // Extract content between the outer braces
          const content = valueStr.substring(1, valueStr.length - 1);

          // Initialize arrays for keys and values
          const keys = [];
          const values = [];

          // Parse the dictionary using a state machine approach
          let currentKey = '';
          let currentValue = '';
          let nestingLevel = 0;
          let inKey = true;

          for (let i = 0; i < content.length; i++) {
            const char = content[i];

            // Track nesting level for brackets
            if (char === '[' || char === '{') {
              nestingLevel++;
              if (!inKey) currentValue += char;
            }
            else if (char === ']' || char === '}') {
              nestingLevel--;
              if (!inKey) currentValue += char;
            }
            // Key-value separator
            else if (char === ':' && nestingLevel === 0 && inKey) {
              inKey = false;
            }
            // Entry separator
            else if (char === ',' && nestingLevel === 0) {
              // Save the current key-value pair
              keys.push(currentKey.trim().replace(/^['"]|['"]$/g, ''));
              values.push(currentValue.trim());

              // Reset for next pair
              currentKey = '';
              currentValue = '';
              inKey = true;
            }
            // Add character to current key or value
            else {
              if (inKey) {
                currentKey += char;
              } else {
                currentValue += char;
              }
            }
          }

          // Add the last key-value pair if there is one
          if (currentKey) {
            keys.push(currentKey.trim().replace(/^['"]|['"]$/g, ''));
            values.push(currentValue.trim());
          }

          // Format entries for display
          const entries = keys.map((key, index) => {
            return {
              rootItem: key,
              bomItems: this.formatNestedValue(values[index])
            };
          });

          return entries;
        } catch (e) {
          console.error("Error parsing dictionary:", e);
          // If parsing fails, return the raw string
          return [valueStr];
        }
      }

      return [valueStr];
    },

    formatNestedValue(valueStr) {
      // Format nested array values more nicely
      if (valueStr.startsWith('[')) {
        try {
          const cleanStr = valueStr
            .replace(/\[\[/g, '')  // Replace double opening brackets
            .replace(/\]\]/g, '')  // Replace double closing brackets
            .replace(/'/g, '')      // Remove quotes
            .replace(/"/g, '')     // Remove double quotes


          // Split by commas
          return cleanStr.split('], [').map(item => item.trim());
        } catch (e) {
          return valueStr;
        }
      }
      return valueStr;
    },
    openGanttModal(plan) {
      this.showGanttModal = true;
      this.selectedPlan = plan;
    },
    closeGanttModal() {
      this.showGanttModal = false;
      this.selectedPlan = null;
    },
    openCriteriaModal(criteria) {
      this.showCriteriaModal = true;
      this.criteria = criteria;
    },
    closeCriteriaModal() {
      this.showCriteriaModal = false;
      this.criteria = null;
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

th,
td {
  padding: 10px;
  border-bottom: 1px solid #ddd;
  border-top: 1px solid #ddd;
  text-align: center;
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
  justify-content: center;
  align-items: center;
}

.button-container button {
  border: none;
  border-radius: 5px;
  cursor: pointer;
  transition: 0.3s;
}

button:hover {
  background: #45a049;
}

.close-btn {
  border: none;
  border-radius: 5px;
  margin-top: 15px;
  background: #d9534f;
  transition: 0.3s;
}

button.sort {
  all: unset;
  color: black;
  margin-left: 5px;
}

.sort:hover {
  color: gray;
}

.modal {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
}

.gantt-container {
  background: #fff;
  border-radius: 10px;
  padding: 20px;
  width: 90%;
  max-height: 90vh;
  overflow: auto;
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
}

.gantt-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 2px solid #eee;
  padding-bottom: 15px;
}

.criteria-container {
  background: #fff;
  border-radius: 10px;
  padding: 20px;
  width: 60%;
  max-height: 90vh;
  overflow: auto;
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
}

.criteria-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 2px solid #eee;
  padding-bottom: 15px;
}

.criteria-header h3 {
  font-size: 35px;
  color: #333;
}

.criteria-list {
  list-style-type: none;
  display: flex;
  flex-direction: column;
}

.criteria-item {
  padding: 12px;
  background-color: #f9f9f9;
  border-radius: 8px;
  border-bottom: 2px solid #eee;
}

.criteria-name {
  font-weight: bold;
  display: block;
  font-size: 20px;
  margin-bottom: 5px;
}

.criteria-values {
  margin-top: 8px;
  margin-left: 15px;
  font-size: 17px;
}

.criteria-values ul {
  list-style-type: disc;
  padding-left: 20px;
}

ul {
  list-style: none;
  padding: 0;
  margin: 0;
}

.bom-group {
  margin-bottom: 10px;
}

.bom-group h3 {
  margin: 10px 0;
  font-size: 18px;
}

.modal-content {
  border: none;
}

.modal-close-btn {
  background-color: #f44336;
  color: white;
  border: none;
  border-radius: 5px;
  cursor: pointer;
  transition: 0.3s;
  padding: 5px 10px;
}

/* Pagination styles */
.pagination {
  display: flex;
  justify-content: center;
  align-items: center;
  margin-top: 20px;
  gap: 15px;
}

.page-button {
  background-color: #4CAF50;
  color: white;
  border: none;
  border-radius: 4px;
  padding: 8px 16px;
  cursor: pointer;
  transition: background-color 0.3s;
}

.page-button:hover:not(:disabled) {
  background-color: #45a049;
}

.page-button:disabled {
  background-color: #cccccc;
  cursor: not-allowed;
}

.page-info {
  font-size: 14px;
  color: #666;
  padding: 5px 10px;
  border-radius: 4px;
  background-color: #f9f9f9;
}

/* Optional: Add page number buttons if you want to jump to specific pages */
.page-number {
  padding: 5px 10px;
  margin: 0 2px;
  border: 1px solid #ddd;
  border-radius: 4px;
  cursor: pointer;
}

.page-number.active {
  background-color: #4CAF50;
  color: white;
  border-color: #4CAF50;
}
</style>