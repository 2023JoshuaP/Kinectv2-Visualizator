# Letras y aplicaciones por señas

La pestaña **Recognize signs** muestra la letra reconocida en grande y sobre la cámara. Los modelos base **LSP** y **ASL** son experimentales: reconocen 24 letras estáticas, no J, Z ni Ñ. **LSE** requiere muestras personales. No es un traductor de lengua de señas ni un reconocimiento validado; las letras parecidas, como M/N/T, pueden confundirse.

## Reconocer una letra

1. Pulsa **Start recognition**. Se activa color y detección de manos automáticamente.
2. Elige el perfil de alfabeto y muestra **una sola mano**, bien iluminada y completamente visible.
3. Consulta **Recognized letter · live result**: es el resultado de la cámara, no la letra seleccionada para configurar una acción. `—` indica que no hay una coincidencia clara.
4. Si una letra falla, selecciónala y pulsa **Record current pose** al menos tres veces, variando ligeramente la pose con la misma mano. Estas muestras tienen prioridad sobre el modelo base y se guardan localmente en `sign-templates.json`, en el directorio de datos de la aplicación Qt. Graba también la otra mano si quieres usarla.

## Abrir aplicaciones

Las acciones están **desactivadas al iniciar**. Primero comprueba que las letras se reconocen correctamente.

| Letra | Acción inicial |
| --- | --- |
| T | Terminal |
| N | Navegador predeterminado |
| C | Calculadora, si está instalada |
| E | Editor de texto, si está instalado |
| F | Archivos, si está instalado |
| V | VS Code o VSCodium, si está instalado |

Para cambiar una asignación, selecciona la **Letter** y la acción en **Action for this session**. Puedes asignar cualquier aplicación detectada a otra letra. **none** elimina la asignación.

**Choose another application…** permite elegir un ejecutable (por ejemplo, `/usr/bin/code` o un AppImage ejecutable), no un archivo `.desktop` ni una línea de comandos. Se asigna a la letra seleccionada y desactiva las acciones para que puedas comprobar el cambio. Los programas se lanzan sin evaluar comandos de shell y sin argumentos adicionales.

Activa **Enable actions**, mantén la letra durante **0,8 segundos** y retira la mano al menos **0,5 segundos** antes del siguiente comando. Hay un mínimo de dos segundos entre ejecuciones. Las asignaciones duran la sesión; las muestras personales sí persisten.

## Profundidad e integración

El filtro opcional **Require wrist distance 0.5–2.5 m**, en las herramientas avanzadas, requiere ambos flujos y **Extended registration**. Si no hay profundidad válida, rechaza la acción. La distancia a la muñeca es aproximada, no geometría precisa de los dedos.

`ActionRegistry` en `sign_commands.py` separa las acciones del reconocimiento. Los adaptadores de red deben usar un worker con tiempos de espera para no bloquear la interfaz. La inferencia de manos procesa el frame más reciente en un hilo independiente.
