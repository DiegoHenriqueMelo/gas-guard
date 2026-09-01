<script setup lang="ts">
import { ref, watch } from 'vue'

const props = withDefaults(
  defineProps<{
    aberto: boolean
    titulo: string
    mensagem: string
    rotuloConfirmar?: string
    perigo?: boolean
  }>(),
  {
    rotuloConfirmar: 'Confirmar',
    perigo: false,
  },
)

const emit = defineEmits<{
  confirmar: []
  cancelar: []
}>()

const dialogo = ref<HTMLDialogElement | null>(null)

// Usamos o <dialog> nativo em vez de uma div com position:fixed porque ele
// traz de graca o que costuma faltar num modal caseiro: prende o foco
// dentro, torna o resto da pagina inerte, fecha no ESC e desenha o
// ::backdrop. So que abrir e fechar sao METODOS (showModal/close), nao um
// atributo reativo - por isso o watch traduz a prop para a chamada.
watch(
  () => props.aberto,
  (aberto) => {
    const el = dialogo.value
    if (!el) return

    if (aberto && !el.open) el.showModal()
    if (!aberto && el.open) el.close()
  },
)
</script>

<template>
  <dialog
    ref="dialogo"
    class="modal"
    aria-labelledby="modal-titulo"
    @cancel.prevent="emit('cancelar')"
    @click.self="emit('cancelar')"
  >
    <div class="conteudo">
      <h2 id="modal-titulo">{{ titulo }}</h2>
      <p>{{ mensagem }}</p>

      <div class="acoes">
        <button type="button" class="gg-btn" @click="emit('cancelar')">
          Cancelar
        </button>
        <button
          type="button"
          class="gg-btn"
          :class="perigo ? 'gg-btn--perigo' : 'gg-btn--primario'"
          @click="emit('confirmar')"
        >
          {{ rotuloConfirmar }}
        </button>
      </div>
    </div>
  </dialog>
</template>

<style scoped>
/* padding zero no proprio <dialog>: assim o @click.self so dispara em
   clique no backdrop, e nao numa borda interna do cartao. */
.modal {
  padding: 0;
  border: 1px solid var(--gg-line);
  border-radius: 8px;
  background: var(--gg-surface);
  color: var(--gg-ink);
  max-width: min(30rem, calc(100vw - 2rem));
  box-shadow: 0 12px 40px -12px rgba(15, 29, 28, 0.45);
}

.modal::backdrop {
  background: rgba(15, 29, 28, 0.45);
}

.conteudo {
  padding: 1.4rem 1.5rem 1.3rem;
}

h2 {
  margin: 0 0 0.6rem;
  font-size: 1.05rem;
  font-weight: 600;
}

p {
  margin: 0;
  font-size: 0.95rem;
  color: var(--gg-ink-2);
  line-height: 1.55;
}

.acoes {
  display: flex;
  justify-content: flex-end;
  gap: 0.6rem;
  margin-top: 1.4rem;
}
</style>
