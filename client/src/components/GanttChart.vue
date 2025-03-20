<template>
  <div>
    <!-- Navigation buttons -->
    <div class="filters">
      <!-- Previous and Next Week Buttons -->
      <button @click="previousWeek" :class="{ 'animate-click': isAnimating === 'previousWeek' }"
        @animationend="resetAnimation" aria-label="Previous Week">
        <font-awesome-icon icon="arrow-left" />
      </button>
      <button @click="nextWeek" :class="{ 'animate-click': isAnimating === 'nextWeek' }" @animationend="resetAnimation"
        aria-label="Next Week">
        <font-awesome-icon icon="arrow-right" />
      </button>
      <button @click="toggleFilters" :class="{ 'animate-click': isAnimating === 'toggleFilters' }"
        @animationend="resetAnimation" aria-label="Filters">
        <font-awesome-icon icon="filter" />
      </button>
      <div v-if="isAlgorithmRunning" class="loading-tooltip">
        <div class="loading-spinner"></div>
        <p style="margin: 0;">A criar novo plano...</p>
      </div>

      <!-- Filters Dropdown Menu -->
      <transition name="fade">
        <div v-if="showFilters" class="filter-menu">
          <!-- Date Filter -->
          <div style="margin-bottom: 10px;">
            <label for="date-filter" style="display: block; font-weight: bold; margin-bottom: 5px;">
              Filtrar por Data
            </label>
            <input id="date-filter" type="month" @change="filterbyDate" style="width: 100%; padding: 5px;" />
          </div>
          <!-- Additional Filters -->
          <div style="margin-bottom: 10px;">
            <label style="font-weight: bold;">Filtrar por Processo</label>
            <div v-if="hasRODMachines">
              <label>
                <input type="checkbox" value="ROD" v-model="selectedMachineTypes" />
                ROD
              </label>
            </div>
            <div>
              <label>
                <input type="checkbox" value="MDW" v-model="selectedMachineTypes" />
                MDW
              </label>
            </div>
            <div>
              <label>
                <input type="checkbox" value="BUN" v-model="selectedMachineTypes" />
                BUN
              </label>
            </div>
          </div>
        </div>
      </transition>
    </div>

    <!-- Gantt Chart -->
    <div :style="{ height: chartHeight + 'px', overflowY: 'auto', position: 'relative' }" @dblclick="resetZoom">
      <Bar v-if="isDataLoaded" ref="ganttChart" :data="data" :options="options" />
      <p v-else style="margin-left: 20px;">A carregar dados...</p>
    </div>
  </div>
</template>

<script lang="ts">
import { Bar } from 'vue-chartjs';
import * as chartConfig from './chartConfig.js';
import { FontAwesomeIcon } from '@fortawesome/vue-fontawesome';

import {
  Chart as ChartJS,
  Title,
  Tooltip,
  Legend,
  BarElement,
  CategoryScale,
  LinearScale,
  TimeScale,
} from 'chart.js';
import 'chartjs-adapter-date-fns';
import zoomPlugin from 'chartjs-plugin-zoom';
import { startOfWeek, endOfWeek, addWeeks, subWeeks } from 'date-fns'; // Import week navigation functions

ChartJS.register(Title, Tooltip, Legend, BarElement, CategoryScale, LinearScale, TimeScale, zoomPlugin);

export default {
  components: { Bar, FontAwesomeIcon },
  props: {
    isLoading: {
      type: Boolean,
      required: true,
    },
  },
  data() {
    return {
      originalData: null as any,
      originalOptions: null as any,
      data: chartConfig.data,
      options: chartConfig.options,
      isDataLoaded: false, // Track loading state
      chartHeight: 0,
      baseHeight: 40, // Height per machine
      padding: 100,
      currentWeekRange: {
        start: null as Date | null,
        end: null as Date | null,
      }, // To keep track of the current week range
      showFilters: false,
      selectedMachineTypes: ['ROD', 'MDW', 'BUN'],
      isAnimating: null as any, // Tracks which button is being animated
      isAlgorithmRunning: false,
    };
  },
  mounted() {
    // Window resize listener to adjust the chart height, in case the window size changes
    window.addEventListener('resize', this.handleResize);
    // Get all the items and machines to populate the chart
    this.fetchData().then(() => {
      this.originalData = JSON.parse(JSON.stringify(this.data));
      this.originalOptions = this.options
    });
  },
  beforeDestroy() {
    window.removeEventListener('resize', this.handleResize);
  },
  computed: {
    hasRODMachines() {
      return this.originalOptions.scales.y.labels.some((label) => label && label.startsWith('ROD'));
    }
  },
  methods: {
    async fetchData() {
      try {
        await chartConfig.getData();
        this.isDataLoaded = true;

        // Update chart height based on data
        this.updateChartHeight();

        // Initialize week range
        const today = new Date();
        this.setWeekRange(today);
      } catch (error) {
        console.error('Error loading Gantt chart data:', error);
      }
    },
    updateChartHeight() {
      // Calculate height based on number of machines or a minimum to fill the screen
      const machineCount = this.options?.scales?.y?.labels?.length || 0;
      const machineBasedHeight = machineCount * this.baseHeight + this.padding;

      // Get viewport height (minus space for header, navigation, etc)
      const viewportHeight = window.innerHeight - 250; // Adjusted to leave some space for other UI elements

      // Use the larger of the two values to ensure minimum height
      this.chartHeight = Math.max(machineBasedHeight, viewportHeight);
    },
    toggleFilters() {
      this.triggerButtonAnimation('toggleFilters');
      this.showFilters = !this.showFilters; 
    },
    setWeekRange(date: Date) {
      const startOfWeekDate = startOfWeek(date, { weekStartsOn: 1 }); // Week starts on Monday
      const endOfWeekDate = endOfWeek(date, { weekStartsOn: 1 }); // Week ends on Sunday

      this.currentWeekRange.start = startOfWeekDate;
      this.currentWeekRange.end = endOfWeekDate;

      // Update chart options with the new date range
      this.options = {
        ...this.options,
        scales: {
          ...this.options.scales,
          x: {
            ...this.options.scales.x,
            min: startOfWeekDate.toISOString(),
            max: endOfWeekDate.toISOString(),
          },
        },
      };

      this.data = { ...this.data };
    },
    previousWeek() {
      this.triggerButtonAnimation('previousWeek');
      if (this.currentWeekRange.start) {
        const newStartDate = subWeeks(this.currentWeekRange.start, 1);
        this.setWeekRange(newStartDate);
      }
    },
    nextWeek() {
      this.triggerButtonAnimation('nextWeek');
      if (this.currentWeekRange.start) {
        const newStartDate = addWeeks(this.currentWeekRange.start, 1);
        this.setWeekRange(newStartDate);
      }
    },
    filterbyDate(event) {
      // Extract the year and month from the input value
      const inputValue = event.target.value;
      const [year, month] = inputValue.split('-');

      // Get the first day of the month
      const startDate = new Date(Number(year), Number(month) - 1, 1);

      // Set the week range for the first week of the month
      this.setWeekRange(startDate);
    },
    filterbyMachine() {
      // Ensure machines are sorted by the defined order
      this.selectedMachineTypes = this.selectedMachineTypes.sort((a, b) => {
        const order = ['ROD', 'MDW', 'BUN'];
        return order.indexOf(a) - order.indexOf(b);
      });

      // Filter datasets based on selected processes
      const filteredDatasets = this.originalData.datasets[0].data.filter((dataset) =>
        this.selectedMachineTypes.some((filter) => dataset.y.startsWith(filter))
      );

      // Filter machines based on selected processes
      const filteredMachines = this.originalOptions.scales.y.labels.filter((label) =>
        this.selectedMachineTypes.some((filter) => label.startsWith(filter))
      );

      // Sort the machines 
      const sortedFilteredMachines = this.selectedMachineTypes.flatMap((type) =>
        filteredMachines.filter((machine) => machine.startsWith(type))
      );

      // Update chart height based on visible machines
      const machineBasedHeight = sortedFilteredMachines.length * this.baseHeight + this.padding;
      const viewportHeight = window.innerHeight - 150;
      this.chartHeight = Math.max(machineBasedHeight, viewportHeight);

      const filterColors = [];
      for (let i = 0; i < filteredDatasets.length; i++) {
        const result = this.originalData.datasets[0].data.indexOf(filteredDatasets[i]);
        const colorsResult = this.originalData.datasets[0].backgroundColor[result];
        filterColors.push(colorsResult);
      }

      // Update the chart data and background colors
      this.data = {
        ...this.originalData,
        datasets: [
          {
            ...this.originalData.datasets[0],
            data: filteredDatasets,
            backgroundColor: filterColors,
          },
        ],
      };

      this.options = {
        ...this.options,
        scales: {
          ...this.options.scales,
          y: {
            ...this.options.scales.y,
            labels: sortedFilteredMachines,
          },
        },
      };
    },
    handleResize() {
      this.updateChartHeight();
    },
    triggerButtonAnimation(buttonName: string) {
      this.isAnimating = buttonName; // Set the button being animated
    },
    resetAnimation() {
      this.isAnimating = null; // Reset the animation state
    },
    resetZoom() {
      const chartComponent = this.$refs.ganttChart;

      if (chartComponent && chartComponent.chart) {
        chartComponent.chart.resetZoom();
      }
    },
  },
  watch: {
    selectedMachineTypes: {
      handler() {
        this.filterbyMachine();
      },
      deep: true,
    },
    isLoading: {
      handler(newVal) {
        this.isAlgorithmRunning = newVal; // Synchronize internal loading state with spinner
      },
      immediate: true,
    },
  },
};
</script>

<style scoped>
.filters {
  text-align: right;
  margin: 5px 5px;
  display: flex;
  justify-content: flex-end;
  align-items: center;
  position: relative;
}

.filter-menu {
  position: absolute;
  top: 50px;
  right: 5px;
  background: white;
  box-shadow: 0px 4px 6px rgba(0, 0, 0, 0.1);
  border: 1px solid #ddd;
  border-radius: 5px;
  padding: 10px;
  z-index: 1000;
}

button {
  background: none;
  cursor: pointer;
  margin: 0 5px;
  margin-bottom: 10px;
  margin-top: 10px;
  border-radius: 5px;
  transition: background-color 0.3s ease, transform 0.2s ease;
}

/* Hover Effect */
button:hover {
  background-color: rgba(0, 0, 0, 0.1);
  transform: scale(1.05);
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter,
.fade-leave-to {
  opacity: 0;
}

.animate-click {
  animation: button-click 0.3s ease;
}

@keyframes button-click {
  0% {
    transform: scale(1);
  }

  50% {
    transform: scale(0.9);
  }

  100% {
    transform: scale(1);
  }
}

.loading-tooltip {
  position: absolute;
  top: 10px;
  left: 10px;
  display: flex;
  align-items: center;
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid #ddd;
  border-radius: 5px;
  padding: 5px 10px;
  box-shadow: 0px 4px 6px rgba(0, 0, 0, 0.1);
}

.loading-spinner {
  border: 3px solid #f3f3f3;
  border-top: 3px solid #3498db;
  border-radius: 50%;
  width: 20px;
  height: 20px;
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
