<script setup>
import * as echarts from 'echarts'
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = defineProps({ option: { type: Object, required: true } })
const host = ref(null)
let chart
let observer

function render() {
  nextTick(() => {
    if (!host.value) return
    chart ||= echarts.init(host.value)
    chart.setOption(props.option, true)
  })
}

onMounted(() => {
  render()
  observer = new ResizeObserver(() => chart?.resize())
  observer.observe(host.value)
})
watch(() => props.option, render, { deep: true })
onBeforeUnmount(() => { observer?.disconnect(); chart?.dispose() })
</script>

<template><div ref="host" class="chart-host" /></template>
