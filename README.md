# Nexus VR

Experiência 3D/VR para a web inspirada na Next VR: menu de entrada cinematográfico,
hub flutuante de aplicativos, skybox panorâmico 360° com cinco ambientes, modo VR
estéreo lado a lado, mini-games 3D, player de vídeo 360° e mãos virtuais com suporte
a rastreamento nativo no iOS.

Construído apenas com **HTML, CSS, JavaScript e Three.js** (r147 vendorizado). Todos os
assets são locais — o app funciona offline e não faz nenhuma chamada a servidores
externos.

---

## Como rodar

O projeto é estático, mas os panoramas e vídeos são carregados por `fetch`/`<video>`,
então precisa de um servidor HTTP local (abrir `index.html` como `file://` bloqueia
as texturas).

```bash
python3 tools/serve.py 5173     # http://localhost:5173
```

Em produção, sirva a raiz do repositório com qualquer servidor estático
(Nginx, GitHub Pages, Cloudflare Pages…).

### Publicar no GitHub Pages

1. Settings → Pages → Source: *Deploy from a branch*.
2. Branch `main`, pasta `/ (root)`.
3. O app fica em `https://<usuario>.github.io/Nexus-vr/`.

Todos os caminhos são relativos, então funciona em qualquer subpasta.

---

## Estrutura

```
index.html                  # shell da aplicação (PT-BR), HUD, painéis
manifest.webmanifest        # PWA: nome, cores, ícones
styles.css                  # (imports) — ver assets/css
assets/
  css/base.css              # tokens, reset, tipografia, layout do entry
  css/ui.css                # HUD, dock, painéis, jogos, player, modos VR
  js/core.js                # namespace NX, utilidades, bus, store, mundos, settings
  js/i18n.js                # textos pt/en
  js/audio.js               # SFX procedurais (Web Audio) + ambiências
  js/xr.js                  # entrada 6DoF: arrasto, giroscópio, ponte nativa, gaze
  js/scene.js               # motor Three.js: sky dome, hub, portais, picking, estéreo
  js/hands.js               # mãos virtuais 17 joints + ingestão nativa
  js/hub.js                 # catálogo de apps, ícones SVG rasterizados
  js/games.js               # Asteroides, Orbes de Luz, Neon Runner
  js/browser.js             # destinos web, player 360, galeria
  js/app.js                 # boot, transições, settings, modal, loop principal
  audio/                    # click.wav, hover.wav, … + ambient-calm.mp3
  fonts/                    # Space Grotesk + Inter (woff2, OFL)
  icons/                    # ícones de app/PWA (png)
  textures/panoramas/       # equiretangulares 2:1 (jpg)
  textures/thumbs/          # miniaturas do seletor de mundos
  vendor/                   # three.min.js r147 + GLTFLoader
  video/                    # space.mp4, aurora.mp4 (equiretangulares 360°)
tools/
  serve.py                  # servidor estático de desenvolvimento
  gen_panoramas.py          # regenera os panoramas
  gen_icons.py              # regenera os ícones
  gen_audio.py              # regenera os SFX (.wav)
  gen_videos.py             # regenera os clipes 360° (.mp4)
docs/
  NATIVE_BRIDGE.md          # contrato WKWebView ↔ JS para ARKit / Vision
```

Os assets são gerados de forma procedural (numpy/PIL/ffmpeg) e ficam versionados,
para que a experiência rode sem nenhuma dependência de rede.

---

## Controles

| Ação | Mouse / toque | Teclado | Gaze / VR |
| --- | --- | --- | --- |
| Olhar | arrastar | setas ← → | mover a cabeça |
| Navegar no carrossel | arrastar para o lado | ← → | — |
| Abrir o app em foco | clicar / tocar | Enter | olhar + pinça |
| Configurações | botão ⚙ | Esc fecha | — |
| VR estéreo | botão óculos | — | — |

Giroscópio: ativado por padrão em dispositivos móveis (pede permissão no iOS).

---

## Modo VR estéreo

O botão de óculos (ou `Enter VR` na tela inicial) ativa a renderização lado a lado
com separação interpupilar (IPD) ajustável. Pensado para óculos de celular
(Cardboard e similares): o app entra em fullscreen e mostra apenas um botão
`SAIR DO VR`. Funciona em retrato e paisagem.

---

## Mãos virtuais e ponte nativa (iOS)

`window.NativeXR` é a ponte usada pelo app nativo em WKWebView. O JS:

* chama `NativeXR.postMessage({ type, payload })` quando disponível;
* escuta eventos `nexus-xr-hands` e `nexus-xr-pose` na `window`;
* aceita também `NX.xr.setPose()` / `NX.xr.setHands()` para testes no navegador.

Detalhes do protocolo, exemplos em Swift e o passo a passo para empacotar como
`.ipa` estão em **[docs/NATIVE_BRIDGE.md](docs/NATIVE_BRIDGE.md)**.

---

## API pública (console)

```js
NX.app.enterFromNative()        // entra direto no hub
NX.app.setWorld("space")        // night | space | beach | cinema | virtual
NX.app.setStereo(true)          // VR lado a lado
NX.app.openSettings()
NX.hub.select(3)                // abre o app do índice
NX.games.begin("orbs")          // asteroids | orbs | neon
NX.player.open("assets/video/aurora.mp4", "Aurora")
window.NexusVR.enter()          // atalhos para o wrapper nativo
```

---

## Compatibilidade

* iOS 14+ (Safari e WKWebView), Android Chrome, desktop Chrome/Safari/Firefox.
* WebGL 1 é suficiente; a qualidade cai automaticamente quando o dispositivo é
  modesto (`quality: auto` → low/medium/high).
* Áudio só inicia após o primeiro toque (política dos navegadores).
* `playsinline`/`muted` no vídeo 360 para o iOS não abrir o player nativo.

---

## Créditos

Fontes: Space Grotesk e Inter (SIL Open Font License).
Three.js r147 (MIT).
Panoramas, ícones, áudio e vídeos são gerados pelos scripts em `tools/`.
