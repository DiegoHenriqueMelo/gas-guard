<script setup lang="ts">
import { RouterLink, RouterView } from 'vue-router'
</script>

<template>
  <div class="app">
    <header class="cabecalho">
      <div class="marca">
        <span class="icone" aria-hidden="true">🧯</span>
        <div>
          <h1>Gas-Guard</h1>
          <p>Monitoramento de vazamento de gás em tempo real</p>
        </div>
      </div>

      <nav class="menu">
        <RouterLink to="/">Painel</RouterLink>
        <RouterLink to="/ambientes">Ambientes</RouterLink>
        <RouterLink to="/dispositivos">Dispositivos</RouterLink>
      </nav>
    </header>

    <main>
      <RouterView />
    </main>

    <footer>
      Leituras publicadas pelo ESP32 via MQTT · série temporal no InfluxDB
    </footer>
  </div>
</template>

<style scoped>
.app {
  max-width: 66rem;
  margin: 0 auto;
  padding: 2rem 1.4rem 4rem;
  display: flex;
  flex-direction: column;
  gap: 1.8rem;
}

.cabecalho {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  justify-content: space-between;
  gap: 1.2rem;
  border-bottom: 1px solid var(--gg-line);
  padding-bottom: 1.1rem;
}

.marca {
  display: flex;
  align-items: center;
  gap: 0.9rem;
}

.icone {
  font-size: 2rem;
  line-height: 1;
}

h1 {
  margin: 0;
  font-size: 1.5rem;
  font-weight: 600;
  letter-spacing: -0.015em;
  color: var(--gg-ink);
}

.marca p {
  margin: 0.15rem 0 0;
  font-size: 0.92rem;
  color: var(--gg-ink-2);
}

.menu {
  display: flex;
  gap: 0.35rem;
}

.menu a {
  padding: 0.4rem 0.85rem;
  border-radius: 5px;
  border: 1px solid transparent;
  font-size: 0.92rem;
  font-weight: 500;
  text-decoration: none;
  color: var(--gg-ink-2);
}

.menu a:hover {
  color: var(--gg-ink);
  background: var(--gg-surface-2);
}

/* o vue-router marca sozinho o link da rota atual */
.menu a.router-link-exact-active {
  color: var(--gg-ink);
  background: var(--gg-surface);
  border-color: var(--gg-line);
}

footer {
  font-size: 0.82rem;
  color: var(--gg-ink-2);
  border-top: 1px solid var(--gg-line-soft);
  padding-top: 1.1rem;
}
</style>
