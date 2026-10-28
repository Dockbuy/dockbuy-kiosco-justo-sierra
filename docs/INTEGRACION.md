# Contrato normalizado de la API (provisional)

## Frontend -> API interna

* `POST /api/auth/login`: JSON `{ "matricula": "202210", "pin": "1234" }` -> `{ access_token, token_type, expires_in, estudiante }`.
* `GET /api/me`: devuelve `{estudiante}` con Bearer.
* `GET /api/charges`: devuelve `{matricula, conceptos, moneda, demo}` con Bearer.
* `POST /api/payments/quote`: JSON `{concept_ids:[36,45]}` con Bearer -> `{conceptos,total,moneda,modo,cobroReal}`.
* `POST /api/auth/logout`: revoca Bearer demo.

## Correspondencia con las pantallas proporcionadas

Entidad `concepto`: `id`, `nombre`, `grupo`, `ciclo`, `periodo`, `importe`, `descuento`, `restante`, `estado`, `fechaVencimiento`. El volcado PHP mostrado utiliza `payments`, `profile_students_id`, `KardexPayment`, `pending_amount`, `total_amount`, `discount_charge`, `period`, etc. La API propuesta es una proyección normalizada propia, **no** una réplica 1:1 verificada del backend universitario.

## Conector futuro

Un gateway local implementará adaptador a la API real, token refresh, mapping a contrato normalizado, tiempos de espera y auditoría sin datos sensibles. La aplicación visual no debe necesitar conocer credenciales administrativas de la universidad.

## Webpay PLUS

Los PDFs del proveedor MIT describen `business` (`id_company`, `id_branch`, `user`, `pwd`), sección `url` (`reference`, `amount`, `moneda`, `canal=W`, `version=IntegraWPP`, `omitir_notif_default`), cifrado AES-128, `Data 0` y endpoint QA `https://qa5.mitec.com.mx/p/gen`. También describen publicaciones de liga y respuestas de transacciones. El módulo de cobro real NO está implementado; habría que construirlo en backend, tras recibir credenciales y confirmar con MIT el procedimiento exacto de cifrado, verificación de callbacks, reconciliación y registro idempotente.
