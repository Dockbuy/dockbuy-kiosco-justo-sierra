# Contrato normalizado de la API

**Modo predeterminado: SIPAA.** La integración real de login y consulta de adeudos se documenta en [SIPAA.md](SIPAA.md). El login usa `{matricula,password}`; el backend envía `username`, `password` y `system_code: "AP"` y conserva `data.token` en memoria por sesión. Los endpoints y ejemplos demo de abajo requieren `KIOSCO_DATA_SOURCE=demo`.

## Frontend -> API interna

* `POST /api/auth/login`: JSON `{ "matricula": "202210", "pin": "1234" }` -> `{ access_token, token_type, expires_in, estudiante }`.
* `GET /api/me`: devuelve `{estudiante}` con Bearer.
* `GET /api/charges`: devuelve `{matricula, conceptos, moneda, demo}` con Bearer.
* `POST /api/payments/quote`: JSON `{concept_ids:[36,45]}` con Bearer -> `{conceptos,total,moneda,modo,cobroReal}`.
* `POST /api/auth/logout`: revoca Bearer demo.

### Flujo ampliado en KioskoJsEMR

`GET /api/charges` devuelve solo pendientes de la base demo, ordenados por `fechaVencimiento` e `id`. Los `concept_ids` de cotización y simulación deben ser un prefijo exacto de esa lista; el servidor rechaza saltos, duplicados y cambios de orden.

* `POST /api/payments/simulate` con Bearer y `{concept_ids, request_id}`: guarda un pago ficticio idempotente y devuelve `{payment, conceptos, reused, printed?, print_error?}`. `conceptos` es la nueva lista pendiente. `request_id` tiene entre 16 y 80 caracteres alfanuméricos, guion o guion bajo.
* `POST /api/billing/lookup` con `{code}`: recupera `{payment, invoice}` mediante el folio aleatorio del QR, sin sesión de alumno.
* `POST /api/billing/invoice` con `{code}`: genera o recupera una única factura de prueba y devuelve `{invoice, reused, printed?, print_error?}`.
* `POST /api/billing/print` con `{code, kind: "payment" | "invoice"}`: reimprime un documento ya guardado.

Las respuestas de pago/factura siguen siendo exitosas si el documento se guardó y solo falló la impresión: `printed:false` permite reimprimir sin repetir la operación. Repetir una operación guardada devuelve `reused:true, print_skipped:true` y no vuelve a imprimir automáticamente.

Todos los documentos son ficticios y llevan avisos de demostración. El XML ilustra CFDI 4.0 sin timbrado, sello ni certificado; no es una integración de facturación fiscal. El QR es un identificador local, no una URL móvil. Ver [PAGOS-DEMO.md](PAGOS-DEMO.md).

## Correspondencia con las pantallas proporcionadas

Entidad `concepto`: `id`, `nombre`, `grupo`, `ciclo`, `periodo`, `importe`, `descuento`, `restante`, `estado`, `fechaVencimiento`. El volcado PHP mostrado utiliza `payments`, `profile_students_id`, `KardexPayment`, `pending_amount`, `total_amount`, `discount_charge`, `period`, etc. La API propuesta es una proyección normalizada propia, **no** una réplica 1:1 verificada del backend universitario.

## Conector SIPAA

`api/sipaa.py` implementa LoginApi y KardexStudent según las imágenes del manual recibido el 10/11/2026. Mantiene tokens individuales en backend, valida y normaliza respuestas y vuelve a consultar saldos en la cotización. Si vence el token, se requiere iniciar sesión; no se conserva la contraseña para renovarlo. El registro de pagos, la pasarela y facturación siguen pendientes.

## Webpay PLUS

Los PDFs del proveedor MIT describen `business` (`id_company`, `id_branch`, `user`, `pwd`), sección `url` (`reference`, `amount`, `moneda`, `canal=W`, `version=IntegraWPP`, `omitir_notif_default`), cifrado AES-128, `Data 0` y endpoint QA `https://qa5.mitec.com.mx/p/gen`. También describen publicaciones de liga y respuestas de transacciones. El módulo de cobro real NO está implementado; habría que construirlo en backend, tras recibir credenciales y confirmar con MIT el procedimiento exacto de cifrado, verificación de callbacks, reconciliación y registro idempotente.
