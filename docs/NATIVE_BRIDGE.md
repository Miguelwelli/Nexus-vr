# Ponte nativa — WKWebView, ARKit e Apple Vision

Este documento descreve o contrato entre o app iOS (Swift) e o Nexus VR rodando
dentro de um `WKWebView`, e o passo a passo para gerar o `.ipa`.

O JavaScript **não depende** da ponte para funcionar: sem ela, o app roda com
arrasto, giroscópio e mãos simuladas. A ponte adiciona 6DoF real e rastreamento
de mãos.

---

## 1. Objetos expostos ao JS

| Objeto | Origem | Para que serve |
| --- | --- | --- |
| `window.NativeXR` | **nativo → JS** (você injeta) | canal único de mensagens do app para a web |
| `window.NexusVR` | JS → nativo | atalhos prontos: `enter`, `exit`, `setWorld`, `setStereo`, `openSettings`, `version` |
| `NX.xr` / `NX.hands` | JS | API interna usada pela ponte |

O JS chama o nativo por **métodos diretos** no objeto `window.NativeXR` — mais
simples de implementar no iOS do que um canal de mensagens, porque você só expõe
funções JavaScript via `WKUserScript`:

```js
NX.native.call("setImmersive", true);   // → window.NativeXR.setImmersive(true)
NX.native.emit("enter", { vr: false }); // → window.NativeXR.emit("enter", {...})
```

Ou seja, o Swift injeta um `WKUserScript` que cria `window.NativeXR` com as
funções desejadas. Se um método não existir, a chamada é ignorada em silêncio —
o app continua funcionando no navegador.

O nativo chama o JS disparando eventos:

```js
window.dispatchEvent(new CustomEvent("nexus-xr-hands", { detail: payload }))
window.dispatchEvent(new CustomEvent("nexus-xr-pose",  { detail: payload }))
```

Equivalentes por API, úteis no console:

```js
NX.xr.setPose({ yaw, pitch, position: { x, y, z } })
NX.xr.setHands({ left: {...}, right: {...} })
```

---

## 2. Canal nativo → JS

### 2.1 Pose 6DoF (ARKit)

`nexus-xr-pose` aceita:

```jsonc
{
  "yaw":   0.12,      // radianos, rotação em torno do eixo Y
  "pitch": -0.05,     // radianos, olhar para cima/baixo
  "roll":  0.0,       // opcional, ignorado no modo retrato
  "position": { "x": 0.0, "y": 0.0, "z": 0.0 }   // metros, até ±1.5
}
```

O JS limita a posição a ±1.5 m em X/Z e ±1.2 m em Y para manter o horizonte
estável. Envie a **rotação absoluta** (não delta) a ~60 Hz.

### 2.2 Mãos (Apple Vision / ARKit Hand Tracking)

`nexus-xr-hands` aceita duas formas:

```jsonc
// A) nomeado — preferido
{
  "left":  { "joints": { "wrist": { "x": 0.0, "y": 0.0, "z": 0.0 }, "indexTip": { … }, … } },
  "right": { "joints": { … } }
}

// B) vetor de 17 pontos, na ordem de JOINT_NAMES
{ "right": { "points": [ { "x": …, "y": …, "z": … }, … ] } }
```

Ordem canônica (`JOINT_NAMES` em `assets/js/hands.js`):

```
wrist, palm,
thumbMetacarpal, thumbProximal, thumbTip,
indexMetacarpal, indexProximal, indexTip,
middleMetacarpal, middleProximal, middleTip,
ringMetacarpal, ringProximal, ringTip,
littleMetacarpal, littleProximal, littleTip
```

**Sistema de coordenadas esperado:** metros, mão canhota/handright com
origem na cabeça, `+x` para a direita, `+y` para cima, `−z` para a frente
(mesmo eixo da câmera Three.js). Se você receber joints normalizados em `0..1`
(ARKit `VNHumanHandPoseObservation`), envie `"normalized": true` e o JS escala
por 1.35:

```jsonc
{ "right": { "normalized": true, "joints": { … } } }
```

Mãos ausentes podem ser omitidas (`{ "left": null }`) ou enviadas vazias. A ponte
considera dados válidos por 2,5 s; depois disso o JS volta para a mão simulada.

### 2.3 Pinça (clique)

O JS detecta a pinça medindo a distância `thumbTip ↔ indexTip`:

* fecha abaixo de **2,2 cm**, rearma acima de **3,6 cm** (histerese);
* emite `pick:click` no objeto sob o raio da mão / retículo;
* emite `hands:pinch` para o jogo ativo.

Não é necessário enviar um evento separado — basta mandar os joints corretos.

---

## 3. Canal JS → nativo

Implemente o handler `nativeXR` no `WKWebView`:

```swift
let config = WKWebViewConfiguration()
config.allowsInlineMediaPlayback = true
config.mediaTypesRequiringUserActionForPlayback = []
config.userContentController.add(self, name: "nativeXR")
```

Mensagens enviadas pelo JS:

Métodos que o JS procura em `window.NativeXR`:

| Método | Argumentos | Quando | Ação sugerida |
| --- | --- | --- | --- |
| `emit(name, detail)` | `"enter"` \| `"exit"` + dados | transições do app | telemetria, háptica, ciclo de vida |
| `setImmersive(bool)` | `true` ao entrar | fullscreen / imersão | esconder a status bar |
| `haptic(ms)` | duração em ms | feedback de UI | `UIImpactFeedbackGenerator` |
| `openURL(url)` | string | link externo pedido | `UIApplication.shared.open` |
| `setHandTracking(bool)` | liga/desliga | mãos | iniciar/parar o rastreamento |
| `setGyro(bool)` | liga/desliga | giroscópio | usar `CMMotionManager` |

`emit` recebe o nome do evento como **primeiro argumento** (não um objeto
`{type, payload}`), o que deixa o Swift bem curto:

```swift
// No WKUserScript, exponha os métodos:
let bridge = """
window.NativeXR = {
  emit: function (name, detail) {
    window.webkit.messageHandlers.nativeXR.postMessage(
      { name: name, detail: detail || {} });
  },
  setImmersive: function (on) {
    window.webkit.messageHandlers.nativeXR.postMessage({ name: 'immersive', detail: !!on });
  },
  haptic: function (ms) {
    window.webkit.messageHandlers.nativeXR.postMessage({ name: 'haptic', detail: ms || 12 });
  },
  openURL: function (url) {
    window.webkit.messageHandlers.nativeXR.postMessage({ name: 'openURL', detail: url });
  },
  setHandTracking: function (on) {
    window.webkit.messageHandlers.nativeXR.postMessage({ name: 'hands', detail: !!on });
  },
  setGyro: function (on) {
    window.webkit.messageHandlers.nativeXR.postMessage({ name: 'gyro', detail: !!on });
  }
};
"""
let script = WKUserScript(source: bridge,
                          injectionTime: .atDocumentStart,
                          forMainFrameOnly: true)
config.userContentController.addUserScript(script)
```

O lado nativo então recebe tudo por um único handler:

```swift
extension WebViewController: WKScriptMessageHandler {
  func userContentController(_ controller: WKUserContentController,
                             didReceive message: WKScriptMessage) {
    guard message.name == "nativeXR",
          let body = message.body as? [String: Any],
          let name = body["name"] as? String else { return }
    let detail = body["detail"]

    switch name {
    case "enter":         startSensors()
    case "exit":          stopSensors()
    case "immersive":     setImmersive(detail as? Bool ?? false)
    case "haptic":        haptic(detail as? Double ?? 12)
    case "openURL":
      if let s = detail as? String, let u = URL(string: s) {
        UIApplication.shared.open(u)
      }
    case "hands":         (detail as? Bool ?? false) ? startHandTracking() : stopHandTracking()
    case "gyro":          (detail as? Bool ?? false) ? startGyro() : stopGyro()
    default: break
    }
  }
}
```

### Injeção das poses

```swift
func pushPose(yaw: Double, pitch: Double, position: simd_float3) {
  let js = """
  window.dispatchEvent(new CustomEvent('nexus-xr-pose', { detail: {
    yaw: \(yaw), pitch: \(pitch),
    position: { x: \(position.x), y: \(position.y), z: \(position.z) }
  }}));
  """
  webView.evaluateJavaScript(js)
}
```

> Dica: envie poses por `evaluateJavaScript` no máximo a 60 Hz e evite fazer isso
> quando o app estiver em background — o WKWebView congela o JS e a fila cresce.

---

## 4. Gerar o `.ipa`

O repositório entrega apenas a web app (HTML/CSS/JS). O `.ipa` é o invólucro
nativo que abre esta pasta.

### Opção A — Capacitor (recomendado)

```bash
npm create @capacitor/app nexus-shell
cd nexus-shell
npx cap add ios

# copie o conteúdo de Nexus-vr para ./www
rsync -a --exclude .git --exclude .devtools --exclude tools \
      ../Nexus-vr/ ./www/

npx cap sync ios
npx cap open ios
```

No Xcode:

1. **Signing & Capabilities** → escolha o time e um bundle id próprio.
2. **Info.plist** → adicione:
   * `NSCameraUsageDescription`
   * `NSMicrophoneUsageDescription` (só se usar voz)
   * `NSMotionUsageDescription` (giroscópio)
   * `UISupportedInterfaceOrientations` incluindo `UIInterfaceOrientationPortrait`
3. **Product → Archive** → *Distribute App* → *Ad Hoc* ou *Development* → gera o `.ipa`.

### Opção B — WKWebView manual

Projeto SwiftUI mínimo com um `UIViewRepresentable` em volta de `WKWebView`
carregando o `index.html` empacotado como *folder reference* e o
`WKScriptMessageHandler` acima. Depois, `Product → Archive`.

> **Importante:** a partir do iOS 14, um `.ipa` precisa ser assinado
> (conta Apple Developer, mesmo que gratuita para uso próprio). Não é possível
> instalar um `.ipa` sem assinatura em um iPhone comum.

### Opção C — PWA (sem `.ipa`)

Abra o site publicado no Safari → *Compartilhar* → **Adicionar à Tela de Início**.
O `manifest.webmanifest` já define `display: standalone`, cor de tema e ícone.
Funciona offline depois do primeiro carregamento (cache do navegador).

---

## 5. Checklist no dispositivo

- [ ] Entrada: banner 3D, botão **Entrar** inicia em fullscreen
- [ ] Hub: carrossel com 7 apps, arrastar para o lado troca o foco
- [ ] ⚙ Configurações: trocar mundo, volume, sensibilidade, escala, qualidade
- [ ] Óculos: modo estéreo lado a lado + botão *Sair do VR*
- [ ] Player 360: vídeo esférico com arrasto para olhar
- [ ] Mini-games: os três abrem, pontuam e voltam ao hub
- [ ] Mãos: com a ponte ativa, as mãos seguem os dedos e a pinça clica
- [ ] Girar o aparelho: HUD e carrossel se reorganizam sem erro
