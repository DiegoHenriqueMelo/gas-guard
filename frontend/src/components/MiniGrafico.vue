<script setup lang="ts">
// Mini grafico (sparkline) desenhado direto num <canvas>. Leve de proposito:
// aparece em todo cartao e no painel da cena 3D, e redesenha a cada leitura.
import { onMounted, ref, watch } from 'vue'

const props = withDefaults(
  defineProps<{ valores: number[]; cor?: string; altura?: number }>(),
  { cor: '#0b6e75', altura: 42 },
)

const tela = ref<HTMLCanvasElement | null>(null)

function desenhar(): void {
  const canvas = tela.value
  if (!canvas) return
  const largura = canvas.clientWidth
  const escala = window.devicePixelRatio || 1
  canvas.width = largura * escala
  canvas.height = props.altura * escala
  const ctx = canvas.getContext('2d')
  if (!ctx) return
  ctx.scale(escala, escala)
  ctx.clearRect(0, 0, largura, props.altura)

  const v = props.valores.filter((x) => Number.isFinite(x))
  if (v.length < 2) return
  const min = Math.min(...v)
  const max = Math.max(...v)
  const faixa = max - min || 1
  const passo = largura / (v.length - 1)
  const y = (x: number) => props.altura - 3 - ((x - min) / faixa) * (props.altura - 6)

  ctx.beginPath()
  v.forEach((x, i) => (i === 0 ? ctx.moveTo(0, y(x)) : ctx.lineTo(i * passo, y(x))))
  ctx.strokeStyle = props.cor
  ctx.lineWidth = 1.6
  ctx.lineJoin = 'round'
  ctx.stroke()

  ctx.lineTo(largura, props.altura)
  ctx.lineTo(0, props.altura)
  ctx.closePath()
  ctx.globalAlpha = 0.1
  ctx.fillStyle = props.cor
  ctx.fill()
}

watch(() => [props.valores, props.cor], desenhar)
onMounted(desenhar)
</script>

<template>
  <canvas ref="tela" class="mini" :style="{ height: `${altura}px` }" aria-hidden="true" />
</template>

<style scoped>
.mini {
  display: block;
  width: 100%;
}
</style>
