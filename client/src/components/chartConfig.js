import { ref, reactive } from 'vue';
import axios from 'axios';
import { startOfWeek, endOfWeek } from 'date-fns';

const apiUrl = `http://${import.meta.env.VITE_FLASK_HOST}:${import.meta.env.VITE_FLASK_PORT}`;

export const machines = ref([]);
const exec_plans = ref([]);
export const data = reactive({
  datasets: [],
});

export const options = reactive({
  responsive: true,
  maintainAspectRatio: false, // Allow flexible height
  layout: {
    padding: {
      left: 100,
      right: 100,
    },
  },

  indexAxis: 'y',
  scales: {
    x: {
      position: 'top',
      type: 'time',
      time: {
        unit: 'day',
        displayFormats: {
          day: 'dd/MM/yyyy', // Format for x-axis ticks
        },
        stepSize: 1,
      },
      min: '',
      max: '',
      ticks: {
        font: {
          weight: 'bold',
        }
      },
    },
    y: {
      type: 'category',
      grid: {
        offset: true,
      },
      ticks: {
        font: {
          weight: 'bold',
        }
      },
    },
  },
  plugins: {
    legend: {
      display: false,
    },
    tooltip: {
      yAlign: 'bottom',
      callbacks: {
        label: function (context) {
          const startTime = context.raw?.x[0];
          const endTime = context.raw?.x[1];
          const itemRelated = context.raw?.name;
          const itemRoot = context.raw?.root;
          const quantity = context.raw?.quantity;
          const orderInc = context.raw?.orderInc;

          // Format the tooltip string
          return [
            `Root: ${itemRoot}`,
            `Item: ${itemRelated}`,
            `Start Time: ${new Date(startTime).toLocaleString()}`,
            `End Time: ${new Date(endTime).toLocaleString()}`,
            `Quantity: ${quantity}`,
            `Reels: ${quantity / orderInc}`
          ];
        },
      },
    },
    zoom: {
      zoom: {
        drag: {
          enabled: true,
          backgroundColor: 'rgba(48, 47, 47, 0.25)',
        },

      }
    },
  },
});

// Create a better color generation function
const generateDistinctColor = (index) => {
  // Use golden ratio for better distribution
  const goldenRatioConjugate = 0.618033988749895;

  // Start with a random hue and use golden ratio to get distinct colors
  let hue = (index * goldenRatioConjugate) % 1;

  // Vary saturation and lightness slightly based on index for even more distinction
  const saturation = 65 + (index % 3) * 8; // Vary between 65-85%
  const lightness = 55 + (index % 5) * 2;  // Vary between 55-70%

  return `hsl(${Math.floor(hue * 360)}, ${saturation}%, ${lightness}%)`;
};

// Function to generate border color
const generateBorderColor = (color) => {
  const hslMatch = color.match(/hsl\((\d+),\s*(\d+)%,\s*(\d+)%\)/);
  if (hslMatch) {
    const [_, h, s, l] = hslMatch;
    // Darker border 
    return `hsl(${h}, ${s}%, ${Math.max(30, Number(l) - 15)}%)`;
  }
  return color;
};

export const getData = async () => {
  const path = `${apiUrl}/getChartData`;
  try {
    const res = await axios.get(path, { withCredentials: true });
    exec_plans.value = res.data.exec_plans;
    machines.value = res.data.machines;

    machines.value.sort((a, b) => {
      const getTypeOrder = (type) => {
        if (type.startsWith("ROD0")) return 1;
        if (type.startsWith("MDW0")) return 2;
        if (type.startsWith("BUN0")) return 3;
        return 5;
      };

      const typeOrderA = getTypeOrder(a.name);
      const typeOrderB = getTypeOrder(b.name);

      if (typeOrderA !== typeOrderB) {
        return typeOrderA - typeOrderB;
      }

      // If machines are the same, sort numerically
      const numA = parseInt(a.name.match(/\d+/)[0]);
      const numB = parseInt(b.name.match(/\d+/)[0]);
      return numA - numB;
    });

    // Ensure the y-axis labels match the machine names
    options.scales.y.labels = machines.value.map((machine, _) => machine.name);

    data.datasets.splice(0, data.datasets.length); // Clear existing data

    // Create a better item to color mapping
    const uniqueItems = [...new Set(exec_plans.value.map(plan => plan.itemRelated))];
    const colorMap = new Map();

    // Pre-generate colors for all unique items
    uniqueItems.forEach((item, index) => {
      colorMap.set(item, generateDistinctColor(index));
    });

    let dt = {
      label: "Plano",
      fill: false,
      data: [],
      backgroundColor: [],
      borderColor: [],
      barPercentage: 0.8,
    };

    let minST = Infinity; // Track the earliest start time
    let maxCoT = -Infinity; // Track the latest completion time

    exec_plans.value.forEach((plan) => {
      const startTime = new Date(plan.ST).getTime();
      const completionTime = new Date(plan.CoT).getTime();

      // Update min and max
      if (startTime < minST) minST = startTime;
      if (completionTime > maxCoT) maxCoT = completionTime;

      let data = {
        x: [
          new Date(plan.ST).toISOString(), // Ensure valid ISO string
          new Date(plan.CoT).toISOString(),
        ],
        y: plan.machine,
        name: plan.itemRelated,
        root: plan.itemRoot,
        quantity: plan.quantity,
        orderInc: plan.orderIncrement,
      };
      dt.data.push(data);

      const color = colorMap.get(plan.itemRelated);
      dt.backgroundColor.push(color);
      dt.borderColor.push(generateBorderColor(color));
    });
    data.datasets.push(dt);

    // Get current date and calculate the start and end of the current week
    const currentDate = new Date();
    const minDate = startOfWeek(currentDate, { weekStartsOn: 1 }); // Monday as the first day of the week
    const maxDate = endOfWeek(currentDate, { weekStartsOn: 1 }); // Sunday as the last day of the week

    // Update x-axis dynamically to show the current week
    options.scales.x.min = minDate.toISOString();
    options.scales.x.max = maxDate.toISOString();
  } catch (error) {
    console.error('Error fetching data:', error);
  }
};
