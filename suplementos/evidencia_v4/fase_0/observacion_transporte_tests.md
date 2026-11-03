# Observación adicional durante la batería actual

Durante la ejecución que generó `tests_current.json` se observó en stderr del servidor HTTP al menos un `ConnectionAbortedError: [WinError 10053]` al escribir la respuesta de `POST /api/simulate`, en `motor/ui.py::send` (`self.wfile.write(data)`). La salida fue devuelta por la herramienta de ejecución; el runner guardó por separado la salida de unittest en `tests_current.log` y no capturó toda la consola de hilos del servidor.

La batería concluyó con 91 métodos, 90 superados, un método de regresión fallido en tres subcasos y cero errores registrados por unittest. **Cero errores de unittest no significa que no hubiera esta excepción de transporte en un hilo HTTP.** Las cinco pruebas de exportación pasaron. Una desconexión del cliente es compatible con el mensaje, pero no se demostró causalidad ni relación con el timeout histórico.

No se modificó el manejador HTTP preexistente ni se ocultó la incidencia. Queda pendiente instrumentar/capturar desconexiones de cliente y determinar si requieren tratamiento específico. Esta observación no invalida por sí sola las cifras de CSV, pero limita una afirmación de ausencia total de incidentes del servidor durante pruebas.
