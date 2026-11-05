"""Catálogo ficticio; conservar IDs para no invalidar los pagos demo ya guardados."""
def concept(id, name, group, date, amount, discount=0, period='01'):
    return {'id':id, 'nombre':name, 'grupo':group, 'ciclo':'2026/2027',
            'periodo':period, 'importe':amount, 'descuento':discount,
            'restante':amount-discount, 'estado':'pendiente', 'fechaVencimiento':date}

CONCEPTS = [
    concept(101, 'REINSCRIPCIÓN CICLO ESCOLAR', 'INSCRIPCIÓN', '2026-08-15', 4500, 500),
    concept(102, 'SEGURO ESCOLAR ANUAL', 'SEGURO ESCOLAR', '2026-08-20', 350),
    concept(103, 'COLEGIATURA SEPTIEMBRE', 'COLEGIATURA', '2026-09-05', 3045, 420, '01'),
    concept(104, 'MATERIAL Y USO DE LABORATORIO', 'LABORATORIO', '2026-09-10', 680),
    concept(105, 'SERVICIOS DE BIBLIOTECA', 'BIBLIOTECA', '2026-09-15', 250),
    concept(106, 'COLEGIATURA OCTUBRE', 'COLEGIATURA', '2026-10-05', 3045, 420, '02'),
    concept(107, 'TRANSPORTE ESCOLAR OCTUBRE', 'TRANSPORTE', '2026-10-10', 1450, 0, '02'),
    concept(108, 'ACTIVIDADES DEPORTIVAS', 'ACTIVIDADES', '2026-10-20', 580),
    concept(45, 'TRANSPORTE BASES SOBRE RUTA COMPLETO', 'TRANSPORTE', '2026-11-01', 2900, 0, '03'),
    concept(36, 'COLEGIATURA REINSCRIPCIÓN PRIMARIA SEXTO', 'COLEGIATURA', '2026-11-30', 3045, 420, '03'),
    concept(109, 'COLEGIATURA DICIEMBRE', 'COLEGIATURA', '2026-12-05', 3045, 420, '04'),
    concept(110, 'RENOVACIÓN DE CREDENCIAL', 'SERVICIOS ESCOLARES', '2026-12-10', 180),
    concept(111, 'COLEGIATURA ENERO', 'COLEGIATURA', '2027-01-05', 3045, 420, '05'),
    concept(112, 'TALLER DE IDIOMAS', 'ACTIVIDADES', '2027-01-15', 850),
    concept(55, 'SERVICIOS COMPLEMENTARIOS EXTRA CLASE ARTÍSTICA', 'SERVICIOS COMPLEMENTARIOS', '2027-02-01', 940, 0, '06'),
    concept(56, 'SERVICIOS COMPLEMENTARIOS MÚSICA CLUB DE BANDA SINFÓNICA', 'SERVICIOS COMPLEMENTARIOS', '2027-04-01', 940, 0, '08'),
]
