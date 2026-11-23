/**
 * Gemeo digital da cozinha, em Three.js puro.
 *
 * Regras que esta classe segue (do enunciado):
 * - A cena muda SO com dados do WebSocket: ela nao conhece o simulador. A
 *   cada quadro ela chama `ler()`, que devolve o que esta no store.
 * - Nao redesenha a cena a cada mensagem: a mensagem so atualiza o store;
 *   o loop de animacao le o store e ajusta cor, rotacao, opacidade.
 * - A posicao 3D de cada dispositivo fica SO aqui (POSICOES), indexada pelo
 *   mesmo codigo do cadastro. Dispositivo cadastrado sem posicao vai para a
 *   prateleira da direita: todo dispositivo aparece.
 * - Repeticao usa InstancedMesh (piso, azulejos, nuvem de gas, fluxo no cano).
 * - O cano sai do botijao e chega exatamente na entrada do fogao, passando
 *   pelo centro do medidor de vazao e da valvula: os pontos sao os mesmos.
 */
import * as THREE from 'three'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'
import { CSS2DObject, CSS2DRenderer } from 'three/addons/renderers/CSS2DRenderer.js'

import type { ConteudoInsight, Dispositivo, Estado } from '../api/types'
import { COR_ESTADO } from '../lib/estado'
import { fmt, UNIDADE_CAMPO } from '../lib/formato'
import type { UltimaLeitura } from '../stores/tempoReal'

export interface DadosQuadro {
  semDados: boolean
  itens: Record<string, { estado: Estado; leitura?: UltimaLeitura; insight?: ConteudoInsight }>
}

type V3 = [number, number, number]

// ---------- onde cada coisa fica (metros; piso em y = 0, parede do fundo em z = -3) ----------
const POSICOES: Record<string, V3> = {
  'GAS-01': [-0.9, 0.3, -2.94],     // perto do piso: o GLP e mais pesado que o ar
  'TEMP-01': [1.9, 1.8, -2.94],
  'UMID-01': [2.7, 1.8, -2.94],
  'LUZ-01': [-3.9, 1.27, -0.35],    // no peitoril da janela
  'VAZAO-01': [-2.1, 1.4, -2.9],    // no meio do cano
  'VALVULA-01': [-1.0, 1.4, -2.9],  // no meio do cano
  'EXAUSTOR-01': [0, 2.95, -2.4],   // em cima do duto da coifa
  'SIRENE-01': [3.2, 2.4, -2.94],
}

// O trajeto do gas: do botijao ate a entrada do fogao. Os pontos de
// VAZAO-01 e VALVULA-01 estao NESTA lista, por isso o cano passa por eles.
const CANO: V3[] = [
  [-3.05, 1.12, -2.55], // saida do botijao B
  [-3.05, 1.4, -2.55],
  [-2.7, 1.4, -2.55],
  [-2.7, 1.4, -2.9],
  POSICOES['VAZAO-01'],
  POSICOES['VALVULA-01'],
  [0.9, 1.4, -2.9],
  [0.9, 0.55, -2.9],    // entrada do fogao, na face de tras dele
]
// o botijao A liga no mesmo coletor
const CANO_A: V3[] = [
  [-3.45, 1.12, -2.55],
  [-3.45, 1.4, -2.55],
  [-3.05, 1.4, -2.55],
]

const ESTADOS_LIGADOS = new Set(['ligado', 'aberta'])

interface Item {
  codigo: string
  tipo: string
  grupo: THREE.Group
  base: THREE.Vector3
  status: THREE.MeshStandardMaterial[] // materiais que mostram a cor do estado
  rotulo: HTMLDivElement
  extra: Record<string, THREE.Object3D>
}

function mat(cor: string | number, extra: THREE.MeshStandardMaterialParameters = {}) {
  return new THREE.MeshStandardMaterial({ color: cor, roughness: 0.7, metalness: 0.1, ...extra })
}

export class CenaCozinha {
  private renderer: THREE.WebGLRenderer
  private rotulos: CSS2DRenderer
  private cena = new THREE.Scene()
  private camera: THREE.PerspectiveCamera
  private controles: OrbitControls
  private relogio = new THREE.Clock()
  private raycaster = new THREE.Raycaster()
  private itens = new Map<string, Item>()
  private quadro = 0
  private ultimoRotulo = 0
  private selecionado: string | null = null
  private observador: ResizeObserver
  private destruido = false

  // elementos do ambiente que reagem aos dados
  private ceu!: THREE.MeshBasicMaterial
  private sol!: THREE.DirectionalLight
  private hemisferio!: THREE.HemisphereLight
  private lampadas: THREE.PointLight[] = []
  private nuvem!: THREE.InstancedMesh
  private nuvemBase: { p: THREE.Vector3; r: number; fase: number }[] = []
  private fluxo!: THREE.InstancedMesh
  private fluxoFase = 0
  private trajeto!: THREE.CurvePath<THREE.Vector3>
  private chamas: THREE.Mesh[] = []
  private auxiliar = new THREE.Object3D()

  private container: HTMLElement
  private ler: () => DadosQuadro
  private aoSelecionar: (codigo: string | null) => void

  constructor(
    container: HTMLElement,
    ler: () => DadosQuadro,
    aoSelecionar: (codigo: string | null) => void,
  ) {
    this.container = container
    this.ler = ler
    this.aoSelecionar = aoSelecionar
    const { clientWidth: w, clientHeight: h } = container
    this.renderer = new THREE.WebGLRenderer({ antialias: true })
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    this.renderer.setSize(w, h)
    this.renderer.shadowMap.enabled = true
    container.appendChild(this.renderer.domElement)

    this.rotulos = new CSS2DRenderer()
    this.rotulos.setSize(w, h)
    this.rotulos.domElement.className = 'cena-rotulos'
    container.appendChild(this.rotulos.domElement)

    this.camera = new THREE.PerspectiveCamera(45, w / h, 0.1, 100)
    this.camera.position.set(6.5, 5.2, 7.5)
    this.controles = new OrbitControls(this.camera, this.rotulos.domElement)
    this.controles.target.set(-0.3, 1.1, -1.2)
    this.controles.maxPolarAngle = Math.PI * 0.49
    this.controles.minDistance = 3
    this.controles.maxDistance = 18
    this.controles.enableDamping = true

    this.cena.background = new THREE.Color('#e9eeed')
    this.montarAmbiente()

    this.rotulos.domElement.addEventListener('click', this.aoClicar)
    this.observador = new ResizeObserver(() => this.redimensionar())
    this.observador.observe(container)
    this.renderer.setAnimationLoop(this.animar)
  }

  // ======================= construcao =======================

  private montarAmbiente(): void {
    const c = this.cena

    this.hemisferio = new THREE.HemisphereLight('#ffffff', '#b9a98f', 0.6)
    c.add(this.hemisferio)
    this.sol = new THREE.DirectionalLight('#fff3d6', 1.2)
    this.sol.position.set(-9, 6, 1)
    this.sol.castShadow = true
    this.sol.shadow.mapSize.set(1024, 1024)
    c.add(this.sol)
    for (const x of [-1.5, 1.8]) {
      const lampada = new THREE.PointLight('#ffe7b8', 0, 9)
      lampada.position.set(x, 2.8, 0)
      this.lampadas.push(lampada)
      c.add(lampada)
    }

    // ---- piso: 16 x 12 ladrilhos numa InstancedMesh (uma chamada de desenho) ----
    const ladrilho = new THREE.BoxGeometry(0.49, 0.02, 0.49)
    const piso = new THREE.InstancedMesh(ladrilho, mat('#ffffff'), 16 * 12)
    let n = 0
    const cor = new THREE.Color()
    for (let i = 0; i < 16; i++) {
      for (let j = 0; j < 12; j++) {
        this.auxiliar.position.set(-3.75 + i * 0.5, 0, -2.75 + j * 0.5)
        this.auxiliar.updateMatrix()
        piso.setMatrixAt(n, this.auxiliar.matrix)
        piso.setColorAt(n, cor.set((i + j) % 2 ? '#d8dcd6' : '#c7ccc5'))
        n++
      }
    }
    piso.receiveShadow = true
    c.add(piso)

    // ---- paredes (fundo e esquerda, com o vao da janela) ----
    const parede = mat('#f4f1ea')
    const caixa = (w: number, h: number, d: number, x: number, y: number, z: number, m = parede) => {
      const malha = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), m)
      malha.position.set(x, y, z)
      malha.receiveShadow = true
      c.add(malha)
      return malha
    }
    caixa(8, 3, 0.1, 0, 1.5, -3.05)
    // parede esquerda em 4 pedacos ao redor da janela (z de -1.2 a 0.5, y de 1.2 a 2.4)
    caixa(0.1, 3, 1.8, -4.05, 1.5, -2.1)
    caixa(0.1, 3, 2.5, -4.05, 1.5, 1.75)
    caixa(0.1, 1.2, 1.7, -4.05, 0.6, -0.35)
    caixa(0.1, 0.6, 1.7, -4.05, 2.7, -0.35)
    caixa(0.18, 0.05, 1.8, -3.95, 1.2, -0.35, mat('#d6d0c4')) // peitoril
    this.ceu = new THREE.MeshBasicMaterial({ color: '#9fd3ff' })
    const janela = new THREE.Mesh(new THREE.PlaneGeometry(1.7, 1.2), this.ceu)
    janela.rotation.y = Math.PI / 2
    janela.position.set(-4.08, 1.8, -0.35)
    c.add(janela)

    // ---- azulejos atras do fogao: outra InstancedMesh ----
    const azulejo = new THREE.BoxGeometry(0.19, 0.19, 0.01)
    const azulejos = new THREE.InstancedMesh(azulejo, mat('#ffffff', { roughness: 0.3 }), 12 * 7)
    n = 0
    for (let i = 0; i < 12; i++) {
      for (let j = 0; j < 7; j++) {
        this.auxiliar.position.set(-1.1 + i * 0.2, 0.95 + j * 0.2, -2.995)
        this.auxiliar.updateMatrix()
        azulejos.setMatrixAt(n, this.auxiliar.matrix)
        azulejos.setColorAt(n, cor.set((i + j) % 3 ? '#e4efee' : '#cfe3e1'))
        n++
      }
    }
    c.add(azulejos)

    // ---- fogao industrial ----
    const fogao = caixa(2, 0.9, 1, 0, 0.45, -2.4, mat('#4b5052', { metalness: 0.6, roughness: 0.4 }))
    fogao.castShadow = true
    caixa(2, 0.04, 1, 0, 0.92, -2.4, mat('#2a2d2e', { metalness: 0.5 }))
    for (const [x, z] of [[-0.55, -2.15], [0.55, -2.15], [-0.55, -2.65], [0.55, -2.65]]) {
      const boca = new THREE.Mesh(new THREE.TorusGeometry(0.14, 0.025, 8, 24), mat('#1b1d1e', { metalness: 0.7 }))
      boca.rotation.x = Math.PI / 2
      boca.position.set(x, 0.96, z)
      c.add(boca)
      const chama = new THREE.Mesh(
        new THREE.ConeGeometry(0.11, 0.18, 16, 1, true),
        new THREE.MeshStandardMaterial({ color: '#3a7bff', emissive: '#2c6bff', emissiveIntensity: 1.4, transparent: true, opacity: 0.85 }),
      )
      chama.position.set(x, 1.03, z)
      this.chamas.push(chama)
      c.add(chama)
    }

    // ---- coifa (tronco de piramide) e duto ate o exaustor ----
    const coifa = new THREE.Mesh(new THREE.CylinderGeometry(0.32, 1.15, 0.6, 4, 1, true), mat('#b9c0c2', { metalness: 0.7, roughness: 0.35, side: THREE.DoubleSide }))
    coifa.rotation.y = Math.PI / 4
    coifa.scale.set(1, 1, 0.6)
    coifa.position.set(0, 2.2, -2.4)
    c.add(coifa)
    const duto = new THREE.Mesh(new THREE.CylinderGeometry(0.22, 0.22, 0.45, 20), mat('#aeb5b7', { metalness: 0.7 }))
    duto.position.set(0, 2.72, -2.4) // vai do topo da coifa (2,5) a base do exaustor (2,95)
    c.add(duto)

    // ---- central de GLP: dois botijoes P45 ----
    for (const x of [-3.45, -3.05]) {
      const botijao = new THREE.Mesh(new THREE.CylinderGeometry(0.17, 0.17, 1.0, 24), mat('#c94a2d', { metalness: 0.3 }))
      botijao.position.set(x, 0.55, -2.55)
      botijao.castShadow = true
      c.add(botijao)
      const topo = new THREE.Mesh(new THREE.SphereGeometry(0.17, 20, 10, 0, Math.PI * 2, 0, Math.PI / 2), botijao.material)
      topo.position.set(x, 1.05, -2.55)
      c.add(topo)
    }

    // ---- o cano: segmentos retos com joelhos, pontos exatos ----
    const materialCano = mat('#d2a31f', { metalness: 0.8, roughness: 0.3 })
    for (const trecho of [CANO, CANO_A]) {
      const pontos = trecho.map((p) => new THREE.Vector3(...p))
      for (let i = 0; i < pontos.length - 1; i++) {
        const a = pontos[i]
        const b = pontos[i + 1]
        const tubo = new THREE.Mesh(new THREE.CylinderGeometry(0.035, 0.035, a.distanceTo(b), 12), materialCano)
        tubo.position.copy(a).add(b).multiplyScalar(0.5)
        tubo.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), b.clone().sub(a).normalize())
        c.add(tubo)
        const joelho = new THREE.Mesh(new THREE.SphereGeometry(0.045, 12, 8), materialCano)
        joelho.position.copy(b)
        c.add(joelho)
      }
    }
    // trajeto por onde as particulas do gas correm
    this.trajeto = new THREE.CurvePath<THREE.Vector3>()
    for (let i = 0; i < CANO.length - 1; i++) {
      this.trajeto.add(new THREE.LineCurve3(new THREE.Vector3(...CANO[i]), new THREE.Vector3(...CANO[i + 1])))
    }
    this.fluxo = new THREE.InstancedMesh(
      new THREE.SphereGeometry(0.028, 8, 6),
      new THREE.MeshBasicMaterial({ color: '#fff6a8' }),
      40,
    )
    c.add(this.fluxo)

    // ---- nuvem de gas: esferas transparentes perto do chao ----
    const N = 140
    this.nuvem = new THREE.InstancedMesh(
      new THREE.SphereGeometry(1, 12, 8),
      new THREE.MeshStandardMaterial({ color: '#b9d86a', transparent: true, opacity: 0, depthWrite: false }),
      N,
    )
    for (let i = 0; i < N; i++) {
      this.nuvemBase.push({
        p: new THREE.Vector3(-1.6 + Math.random() * 3.6, 0.08 + Math.random() * 0.5, -2.8 + Math.random() * 2.8),
        r: 0.15 + Math.random() * 0.25,
        fase: Math.random() * Math.PI * 2,
      })
    }
    c.add(this.nuvem)
  }

  /** (Re)cria os dispositivos do cadastro. Chamado quando o cadastro muda. */
  definirDispositivos(dispositivos: Dispositivo[]): void {
    for (const item of this.itens.values()) {
      this.cena.remove(item.grupo)
      item.rotulo.remove()
    }
    this.itens.clear()

    let prateleira = 0
    for (const d of dispositivos) {
      const posicao = POSICOES[d.codigo] ?? [3.85, 0.5 + 0.45 * (prateleira % 5), -2 + 0.6 * Math.floor(prateleira++ / 5)]
      const item = this.criarItem(d, new THREE.Vector3(...posicao))
      this.itens.set(d.codigo, item)
      this.cena.add(item.grupo)
    }
  }

  private criarItem(d: Dispositivo, posicao: THREE.Vector3): Item {
    const grupo = new THREE.Group()
    grupo.position.copy(posicao)
    grupo.userData.codigo = d.codigo
    const status: THREE.MeshStandardMaterial[] = []
    const extra: Record<string, THREE.Object3D> = {}

    const led = () => {
      const m = mat(COR_ESTADO.sem_dados, { emissive: COR_ESTADO.sem_dados, emissiveIntensity: 0.9 })
      status.push(m)
      return m
    }

    if (d.tipo === 'exaustor') {
      const carcaca = new THREE.Mesh(new THREE.CylinderGeometry(0.42, 0.42, 0.28, 32, 1, true), mat('#7f8a8d', { metalness: 0.6, side: THREE.DoubleSide }))
      grupo.add(carcaca)
      const anel = new THREE.Mesh(new THREE.TorusGeometry(0.43, 0.035, 8, 40), led())
      anel.rotation.x = Math.PI / 2
      anel.position.y = 0.14
      grupo.add(anel)
      const rotor = new THREE.Group()
      for (let i = 0; i < 6; i++) {
        const pa = new THREE.Mesh(new THREE.BoxGeometry(0.34, 0.02, 0.11), mat('#d5dadb', { metalness: 0.5 }))
        pa.position.x = 0.19
        pa.rotation.x = 0.35
        const braco = new THREE.Group()
        braco.rotation.y = (i / 6) * Math.PI * 2
        braco.add(pa)
        rotor.add(braco)
      }
      rotor.add(new THREE.Mesh(new THREE.CylinderGeometry(0.06, 0.06, 0.08, 16), mat('#3b4143')))
      rotor.position.y = 0.05
      grupo.add(rotor)
      extra.rotor = rotor
    } else if (d.tipo === 'valvula') {
      grupo.add(new THREE.Mesh(new THREE.BoxGeometry(0.2, 0.16, 0.16), mat('#5d6a6c', { metalness: 0.6 })))
      const alavanca = new THREE.Mesh(new THREE.BoxGeometry(0.04, 0.04, 0.28), led())
      alavanca.position.set(0, 0.12, 0.08)
      grupo.add(alavanca)
      extra.alavanca = alavanca
    } else if (d.tipo === 'sirene') {
      grupo.add(new THREE.Mesh(new THREE.CylinderGeometry(0.12, 0.14, 0.08, 20), mat('#2f3436')))
      const domo = new THREE.Mesh(new THREE.SphereGeometry(0.12, 20, 12, 0, Math.PI * 2, 0, Math.PI / 2), mat('#7a1d14', { emissive: '#ff2a12', emissiveIntensity: 0, transparent: true, opacity: 0.9 }))
      domo.position.y = 0.04
      grupo.add(domo)
      const luz = new THREE.PointLight('#ff3b1f', 0, 5)
      luz.position.set(0, 0.15, 0.2)
      grupo.add(luz)
      const halo = new THREE.Mesh(new THREE.TorusGeometry(0.16, 0.02, 8, 28), led())
      halo.position.z = 0.02
      grupo.add(halo)
      grupo.rotation.x = Math.PI / 2
      extra.domo = domo
      extra.luz = luz
    } else if (d.tipo === 'vazao') {
      grupo.add(new THREE.Mesh(new THREE.BoxGeometry(0.22, 0.14, 0.14), mat('#2d6f73')))
      const visor = new THREE.Mesh(new THREE.CircleGeometry(0.045, 20), led())
      visor.position.z = 0.072
      grupo.add(visor)
    } else {
      // sensor de parede generico: caixinha com LED de estado
      const corpo = new THREE.Mesh(new THREE.BoxGeometry(0.2, 0.14, 0.06), mat('#f7f7f5'))
      grupo.add(corpo)
      const luzLed = new THREE.Mesh(new THREE.SphereGeometry(0.03, 12, 8), led())
      luzLed.position.set(0.06, 0.03, 0.035)
      grupo.add(luzLed)
      const anel = new THREE.Mesh(new THREE.RingGeometry(0.15, 0.18, 32), led())
      anel.position.z = 0.032
      grupo.add(anel)
      if (d.tipo === 'luminosidade') grupo.rotation.y = Math.PI / 2
    }

    const rotulo = document.createElement('div')
    rotulo.className = 'cena-rotulo'
    rotulo.textContent = d.codigo
    const objetoRotulo = new CSS2DObject(rotulo)
    // vizinhos (vazao x valvula no cano, temperatura x umidade na parede):
    // um rotulo acima e o outro abaixo, para nao se encostarem
    const ABAIXO = new Set(['vazao', 'temperatura'])
    const altura = d.tipo === 'exaustor' ? 0.45 : ABAIXO.has(d.tipo) ? -0.24 : 0.26
    objetoRotulo.position.set(0, altura, d.tipo === 'sirene' ? -0.2 : 0)
    grupo.add(objetoRotulo)
    rotulo.addEventListener('click', (evento) => {
      evento.stopPropagation()
      this.selecionar(d.codigo)
    })

    return { codigo: d.codigo, tipo: d.tipo, grupo, base: posicao.clone(), status, rotulo, extra }
  }

  // ======================= animacao =======================

  private animar = (): void => {
    if (this.destruido) return
    const dt = Math.min(this.relogio.getDelta(), 0.1)
    const t = this.relogio.elapsedTime
    const dados = this.ler()
    const vivo = !dados.semDados
    this.quadro++

    // ---- ambiente: dia e noite pela luminosidade da janela ----
    const lux = dados.itens['LUZ-01']?.leitura?.leituras.lux
    const dia = vivo && lux !== undefined ? THREE.MathUtils.clamp((lux - 20) / 600, 0, 1) : 0.5
    this.ceu.color.lerpColors(new THREE.Color('#0d1633'), new THREE.Color('#9fd3ff'), dia)
    this.sol.intensity = 0.1 + 1.4 * dia
    this.hemisferio.intensity = 0.35 + 0.45 * dia
    for (const lampada of this.lampadas) lampada.intensity = THREE.MathUtils.lerp(lampada.intensity, dia < 0.35 ? 6 : 0, 0.05)
    ;(this.cena.background as THREE.Color).lerpColors(new THREE.Color('#1c2333'), new THREE.Color('#e9eeed'), dia)

    // ---- gas: nuvem perto do chao, mais densa quanto maior o ppm ----
    const ppm = vivo ? (dados.itens['GAS-01']?.leitura?.leituras.ppm ?? 0) : 0
    const densidade = THREE.MathUtils.clamp((ppm - 400) / 2600, 0, 1)
    const materialNuvem = this.nuvem.material as THREE.MeshStandardMaterial
    materialNuvem.opacity = THREE.MathUtils.lerp(materialNuvem.opacity, 0.32 * densidade, 0.08)
    this.nuvem.visible = materialNuvem.opacity > 0.01
    if (this.nuvem.visible) {
      const ativos = Math.ceil(this.nuvemBase.length * Math.max(densidade, 0.15))
      this.nuvemBase.forEach((b, i) => {
        const escala = i < ativos ? b.r * (0.7 + densidade) : 0.0001
        this.auxiliar.position.set(b.p.x + Math.sin(t * 0.3 + b.fase) * 0.15, b.p.y + Math.sin(t * 0.5 + b.fase) * 0.05, b.p.z + Math.cos(t * 0.25 + b.fase) * 0.15)
        this.auxiliar.scale.setScalar(escala)
        this.auxiliar.updateMatrix()
        this.nuvem.setMatrixAt(i, this.auxiliar.matrix)
      })
      this.nuvem.instanceMatrix.needsUpdate = true
    }

    // ---- fluxo no cano e chamas: pela vazao medida ----
    const vazao = vivo ? (dados.itens['VAZAO-01']?.leitura?.leituras.vazao ?? 0) : 0
    this.fluxo.visible = vazao > 0.02
    if (this.fluxo.visible) {
      this.fluxoFase = (this.fluxoFase + dt * (0.04 + vazao * 0.06)) % 1
      for (let i = 0; i < 40; i++) {
        this.trajeto.getPointAt((this.fluxoFase + i / 40) % 1, this.auxiliar.position)
        this.auxiliar.scale.setScalar(1)
        this.auxiliar.updateMatrix()
        this.fluxo.setMatrixAt(i, this.auxiliar.matrix)
      }
      this.fluxo.instanceMatrix.needsUpdate = true
    }
    const tamanhoChama = THREE.MathUtils.clamp(vazao / 1.5, 0, 1.3)
    this.chamas.forEach((chama, i) => {
      chama.visible = tamanhoChama > 0.05
      chama.scale.set(1, tamanhoChama * (0.85 + 0.15 * Math.sin(t * 13 + i)), 1)
    })

    // ---- cada dispositivo ----
    for (const item of this.itens.values()) {
      const info = dados.itens[item.codigo]
      const estado: Estado = vivo && info ? info.estado : 'sem_dados'
      const cor = new THREE.Color(COR_ESTADO[estado])
      for (const m of item.status) {
        m.color.copy(cor)
        m.emissive.copy(cor)
        m.emissiveIntensity = item.codigo === this.selecionado ? 1.6 + 0.6 * Math.sin(t * 6) : 0.8
      }
      const leitura = vivo ? info?.leitura : undefined
      const ligado = leitura?.estado ? ESTADOS_LIGADOS.has(leitura.estado) : false

      if (item.tipo === 'exaustor') {
        const rpm = leitura?.leituras.rpm ?? 0
        const rotor = item.extra.rotor
        if (rotor && leitura?.estado === 'ligado') rotor.rotation.y += dt * (rpm / 60) * Math.PI * 2 * 0.25
        // treme mais quanto maior a vibracao (acima do normal de ~1,8 mm/s)
        const vibracao = leitura?.estado === 'ligado' ? (leitura.leituras.vibracao ?? 0) : 0
        // saudavel (ate ~2,2 mm/s) nao treme; dali para cima, cada vez mais
        const amplitude = THREE.MathUtils.clamp((vibracao - 2.2) * 0.007, 0, 0.06)
        item.grupo.position.set(
          item.base.x + (Math.random() - 0.5) * amplitude,
          item.base.y + (Math.random() - 0.5) * amplitude * 0.6,
          item.base.z + (Math.random() - 0.5) * amplitude,
        )
      } else if (item.tipo === 'valvula') {
        const alavanca = item.extra.alavanca
        // alavanca alinhada com o cano = aberta; atravessada = fechada
        if (alavanca) alavanca.rotation.y = THREE.MathUtils.lerp(alavanca.rotation.y, ligado ? Math.PI / 2 : 0, 0.15)
      } else if (item.tipo === 'sirene') {
        const piscando = ligado && Math.sin(t * 10) > 0
        const domo = item.extra.domo as THREE.Mesh
        ;(domo.material as THREE.MeshStandardMaterial).emissiveIntensity = piscando ? 2.2 : 0.05
        ;(item.extra.luz as THREE.PointLight).intensity = piscando ? 8 : 0
      }
    }

    // ---- rotulos: texto atualizado 4x por segundo, nao a cada quadro ----
    if (t - this.ultimoRotulo > 0.25) {
      this.ultimoRotulo = t
      for (const item of this.itens.values()) {
        const info = dados.itens[item.codigo]
        item.rotulo.dataset.estado = vivo && info ? info.estado : 'sem_dados'
        item.rotulo.textContent = `${item.codigo}${vivo ? this.resumo(item, info) : ''}`
      }
    }

    this.controles.update()
    this.renderer.render(this.cena, this.camera)
    this.rotulos.render(this.cena, this.camera)
  }

  private resumo(item: Item, info: DadosQuadro['itens'][string] | undefined): string {
    const leitura = info?.leitura
    if (!leitura) return ''
    if (item.tipo === 'exaustor') {
      const saude = info?.insight?.saude
      return ` · ${leitura.estado ?? ''}${typeof saude === 'number' && info?.insight?.estado_ia === 'ok' ? ` · saúde ${fmt(saude, 0)}` : ''}`
    }
    if (leitura.estado) return ` · ${leitura.estado}`
    const [campo, valor] = Object.entries(leitura.leituras)[0] ?? []
    return campo ? ` · ${fmt(valor, campo === 'ppm' || campo === 'lux' ? 0 : 1)} ${UNIDADE_CAMPO[campo] ?? ''}` : ''
  }

  // ======================= interacao =======================

  private aoClicar = (evento: MouseEvent): void => {
    const area = this.renderer.domElement.getBoundingClientRect()
    const ponteiro = new THREE.Vector2(
      ((evento.clientX - area.left) / area.width) * 2 - 1,
      -((evento.clientY - area.top) / area.height) * 2 + 1,
    )
    this.raycaster.setFromCamera(ponteiro, this.camera)
    const grupos = [...this.itens.values()].map((i) => i.grupo)
    const acerto = this.raycaster.intersectObjects(grupos, true)[0]
    let alvo: THREE.Object3D | null = acerto?.object ?? null
    while (alvo && !alvo.userData.codigo) alvo = alvo.parent
    this.selecionar((alvo?.userData.codigo as string | undefined) ?? null)
  }

  selecionar(codigo: string | null): void {
    this.selecionado = codigo
    this.aoSelecionar(codigo)
  }

  private redimensionar(): void {
    const { clientWidth: w, clientHeight: h } = this.container
    if (!w || !h) return
    this.camera.aspect = w / h
    this.camera.updateProjectionMatrix()
    this.renderer.setSize(w, h)
    this.rotulos.setSize(w, h)
  }

  destruir(): void {
    this.destruido = true
    this.renderer.setAnimationLoop(null)
    this.observador.disconnect()
    this.rotulos.domElement.removeEventListener('click', this.aoClicar)
    this.controles.dispose()
    this.cena.traverse((objeto) => {
      const malha = objeto as THREE.Mesh
      malha.geometry?.dispose()
      const material = malha.material as THREE.Material | THREE.Material[] | undefined
      if (Array.isArray(material)) material.forEach((m) => m.dispose())
      else material?.dispose()
    })
    this.renderer.dispose()
    this.renderer.domElement.remove()
    this.rotulos.domElement.remove()
  }
}
