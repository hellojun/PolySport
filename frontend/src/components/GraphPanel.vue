<template>
  <div class="graph-panel">
    <div class="graph-header">
      <h3 class="graph-title">{{ t('graph.title') }}</h3>
      <div class="graph-controls"></div>
    </div>

    <div ref="graphContainer" class="graph-container">
      <div v-if="!hasData" class="graph-placeholder">
        <span>{{ t('graph.waiting') }}</span>
      </div>
    </div>

    <!-- 图例 -->
    <div v-if="hasData" class="graph-legend">
      <span class="legend-title">{{ t('graph.entity_types') }}</span>
      <span v-for="(color, label) in legendItems" :key="label" class="legend-item">
        <span class="legend-dot" :style="{ background: color }"></span>
        {{ label }}
      </span>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { Network } from 'vis-network'
import { DataSet } from 'vis-data'

const { t } = useI18n()

const props = defineProps({
  graphData: { type: Object, default: null },
})

const graphContainer = ref(null)
const showEdgeLabels = ref(true)
const hasData = ref(false)

let network = null
let nodesDataSet = null
let edgesDataSet = null
let lastNodeCount = 0
let lastEdgeCount = 0

// 实体类型颜色映射
const TYPE_COLORS = {
  Team: '#FF6B35',
  Player: '#4ECDC4',
  Coach: '#45B7D1',
  Arena: '#96CEB4',
  Injury: '#FF6B6B',
  GameRecord: '#C9B1FF',
  Division: '#FFEAA7',
  Season: '#DFE6E9',
  Person: '#FD79A8',
  Organization: '#6C5CE7',
}
const DEFAULT_COLOR = '#B2BEC3'

const legendItems = ref({})

function getNodeColor(labels) {
  if (!labels || labels.length === 0) return DEFAULT_COLOR
  for (const label of labels) {
    if (TYPE_COLORS[label]) return TYPE_COLORS[label]
  }
  return DEFAULT_COLOR
}

function getEntityLabel(labels) {
  if (!labels) return 'Unknown'
  for (const label of labels) {
    if (label !== 'Entity' && label !== 'Node') return label
  }
  return labels[0] || 'Unknown'
}

function buildGraph(data, force = false) {
  if (!data || !data.nodes || data.nodes.length === 0) return

  // 如果节点和边数量没变，跳过重建（避免轮询导致反复重建）
  const nc = data.nodes.length
  const ec = (data.edges || []).length
  if (!force && nc === lastNodeCount && ec === lastEdgeCount && network) return
  lastNodeCount = nc
  lastEdgeCount = ec

  hasData.value = true
  const typesFound = {}

  const nodes = data.nodes.map((n) => {
    const label = getEntityLabel(n.labels)
    const color = getNodeColor(n.labels)
    typesFound[label] = color
    return {
      id: n.uuid,
      label: n.name || '?',
      color: {
        background: color,
        border: color,
        highlight: { background: color, border: '#000' },
      },
      font: { color: '#333', size: 12 },
      shape: 'dot',
      size: 16,
      title: `${label}: ${n.name}\n${n.summary || ''}`,
    }
  })

  const edges = data.edges.map((e) => ({
    id: e.uuid,
    from: e.source_node_uuid,
    to: e.target_node_uuid,
    label: showEdgeLabels.value ? (e.name || '') : '',
    arrows: 'to',
    color: { color: '#B2BEC3', highlight: '#FF4500' },
    font: { size: 9, color: '#999', strokeWidth: 0 },
    smooth: { type: 'continuous' },
  }))

  legendItems.value = typesFound

  nodesDataSet = new DataSet(nodes)
  edgesDataSet = new DataSet(edges)

  nextTick(() => {
    if (!graphContainer.value) return

    const options = {
      physics: {
        solver: 'forceAtlas2Based',
        forceAtlas2Based: {
          gravitationalConstant: -30,
          centralGravity: 0.005,
          springLength: 120,
          springConstant: 0.04,
        },
        stabilization: { iterations: 150 },
      },
      interaction: {
        hover: true,
        tooltipDelay: 200,
        zoomView: false,
        dragView: true,
      },
      edges: {
        width: 1,
        selectionWidth: 2,
      },
    }

    if (network) {
      network.destroy()
    }

    network = new Network(
      graphContainer.value,
      { nodes: nodesDataSet, edges: edgesDataSet },
      options,
    )

    // 稳定化完成后关闭物理引擎，节点不再移动
    network.on('stabilizationIterationsDone', () => {
      network.setOptions({ physics: false })
    })
  })
}

function updateEdgeLabels() {
  if (!edgesDataSet) return
  const updates = edgesDataSet.getIds().map((id) => {
    const edge = edgesDataSet.get(id)
    return {
      id,
      label: showEdgeLabels.value ? (edge._originalLabel || edge.label || '') : '',
    }
  })
  // 先存储原始 label
  if (showEdgeLabels.value) {
    edgesDataSet.forEach((e) => { e._originalLabel = e.label })
  }
  edgesDataSet.update(updates)
}

function refreshGraph() {
  if (props.graphData) {
    buildGraph(props.graphData, true)
  }
}

watch(
  () => props.graphData,
  (newVal) => {
    if (newVal) buildGraph(newVal)
  },
  { deep: true },
)

onMounted(() => {
  if (props.graphData) buildGraph(props.graphData)
})

onBeforeUnmount(() => {
  if (network) {
    network.destroy()
    network = null
  }
})
</script>

<style scoped>
.graph-panel {
  border: 1px solid #E5E5E5;
  background: #FAFAFA;
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 400px;
}

.graph-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid #E5E5E5;
  background: #FFF;
}

.graph-title {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.8rem;
  font-weight: 600;
  margin: 0;
  color: #333;
}

.graph-controls {
  display: flex;
  align-items: center;
  gap: 12px;
}

.ctrl-btn {
  background: none;
  border: 1px solid #DDD;
  padding: 4px 12px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem;
  cursor: pointer;
  color: #666;
  transition: all 0.2s;
}

.ctrl-btn:hover {
  border-color: #333;
  color: #333;
}

.ctrl-label {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem;
  color: #666;
  display: flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
}

.graph-container {
  flex: 1;
  min-height: 350px;
  position: relative;
}

.graph-placeholder {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #CCC;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.85rem;
}

.graph-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  padding: 10px 16px;
  border-top: 1px solid #E5E5E5;
  background: #FFF;
  align-items: center;
}

.legend-title {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.65rem;
  color: #FF4500;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem;
  color: #666;
}

.legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}
</style>
