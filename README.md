# Kinect v2 Explorer

Aplicación PyQt6 para ver color, infrarrojo y profundidad del **Kinect v2**, consultar la calibración, reconocer manos y gestos con MediaPipe y guardar capturas `.npz`. Usa `libfreenect2` mediante `pylibfreenect2`.

## Primera instalación

Sigue la [guía de instalación](GUIA_COMPLETA.md#instalación-y-compilación) para preparar las dependencias y el entorno Python. Completa también los [permisos USB con `udev`](GUIA_COMPLETA.md#permisos-usb-persistentes): sin ellos puede aparecer `LIBUSB_ERROR_ACCESS` aunque el Kinect figure en `lsusb`.

## Ejecutar

Conecta el Kinect directamente a un puerto USB 3 y, desde la raíz del repositorio, ejecuta:

```bash
sh run.sh
```

El lanzador usa `.venv` si existe o el entorno Micromamba `kinectv2-dev`, y configura las bibliotecas locales automáticamente. Puedes abrir la interfaz sin sensor, pero no capturar. No la ejecutes con `sudo`.

Cierra `Protonect` u otros programas que usen el Kinect antes de pulsar **Start capture**. Detén la captura antes de desconectarlo. Si falla, consulta el [diagnóstico](GUIA_COMPLETA.md#resolución-de-problemas).

## Uso

Para ver letras en directo y abrir terminal, navegador u otras aplicaciones, consulta [Letras y aplicaciones por señas](app/SIGN_COMMANDS.md). En **Recognize signs**, pulsa **Start recognition**; comprueba el resultado antes de activar **Enable actions**.

1. Selecciona el dispositivo (**Refresh devices** si hace falta), los flujos y la pipeline. CPU funciona sin GPU; las demás dependen de la compilación.
2. Ajusta profundidad, filtros, exposición o LED antes de iniciar. Pulsa **Start capture**; detén la captura para cambiar estos ajustes.
3. Ajusta **preview FPS** para limitar el trabajo de la interfaz. **Capabilities** muestra los métodos disponibles y los flujos capturados.
4. Activa **Extended registration** antes de iniciar si necesitas profundidad a resolución de color y el mapa de correspondencia. Haz clic en profundidad para consultar XYZ y el píxel color asociado.
5. **Save frame data (.npz)** guarda arrays originales, metadatos y calibración para NumPy.

### Manos y gestos

En **Hand analysis**, elige un modo antes de iniciar; requiere **Color stream**:

| Modo | Resultado |
| --- | --- |
| **Off** | Sin inferencia. |
| **Landmarks** | Los 21 puntos de cada mano, usando `app/hand_landmarker.task`. |
| **Gestures** | `Closed_Fist`, `Open_Palm`, `Pointing_Up`, `Thumb_Down`, `Thumb_Up`, `Victory` e `ILoveYou`, usando `app/gesture_recognizer.task`. |

Los resultados aparecen sobre **Color**. Con **Extended registration**, se añade la distancia aproximada a la muñeca cuando hay profundidad válida. La inferencia funciona en un hilo independiente y procesa el frame más reciente; descarta los intermedios si no alcanza la velocidad de captura. Los gestos son estáticos: movimientos o clases propias requieren un modelo entrenado para ello. No necesitas PyTorch.

### Controles RGB avanzados

**Advanced RGB setting** permite leer/escribir comandos de `ColorSettingCommand` con el flujo color activo. Selecciona **Float** para valores de coma flotante, como `GET_FRAME_RATE` (`30.0`); como entero muestra sus bits. Un mensaje «sent» solo confirma el envío, no que el firmware haya aplicado el cambio.

Para consumir capturas, integrar el binding o consultar sus límites, ve a [Comenzar a desarrollar](GUIA_COMPLETA.md#comenzar-a-desarrollar).
