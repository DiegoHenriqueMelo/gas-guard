<script setup lang="ts">
// A resposta do LLM e texto NAO CONFIAVEL: o modelo pode repetir qualquer
// coisa que estiver nos dados, inclusive algo que pareca HTML ou script.
// Por isso o Markdown e renderizado com:
//   html: false   -> qualquer <tag> sai escapada, como texto
//   sem imagens   -> nada de ![](http://...) carregando URL de fora
//   links         -> so http(s), abrindo em outra aba, sem referrer
import MarkdownIt from 'markdown-it'
import { computed } from 'vue'

const md = new MarkdownIt({ html: false, linkify: false, breaks: true })
md.disable('image')

const padraoLink = md.renderer.rules.link_open ?? ((tokens, i, opcoes, _env, self) => self.renderToken(tokens, i, opcoes))
md.renderer.rules.link_open = (tokens, i, opcoes, env, self) => {
  const token = tokens[i]
  const href = String(token.attrGet('href') ?? '')
  if (!/^https?:\/\//i.test(href)) token.attrSet('href', '#')
  token.attrSet('target', '_blank')
  token.attrSet('rel', 'noopener noreferrer nofollow')
  return padraoLink(tokens, i, opcoes, env, self)
}

const props = defineProps<{ texto: string }>()

// seguro para v-html: com html:false o markdown-it escapa todo HTML de entrada
const html = computed(() => md.render(props.texto))
</script>

<template>
  <!-- eslint-disable-next-line vue/no-v-html -->
  <div class="markdown" v-html="html" />
</template>

<style scoped>
.markdown :deep(p) {
  margin: 0 0 0.6rem;
}
.markdown :deep(p:last-child) {
  margin-bottom: 0;
}
.markdown :deep(ul),
.markdown :deep(ol) {
  margin: 0.3rem 0 0.6rem;
  padding-left: 1.3rem;
}
.markdown :deep(code) {
  font-family: var(--gg-mono);
  font-size: 0.88em;
  background: var(--gg-surface-2);
  padding: 0.05em 0.3em;
  border-radius: 3px;
}
</style>
