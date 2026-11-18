# Open questions about the manual

Points the ABB ACS580 firmware manual (3AXD50000016097 Rev J) leaves open for the shipped
`acs580_overtemperature` graph. Each one is recorded in the graph file as an `open_questions`
entry on its cause, together with the manual reference that would settle it. Until then the
graph takes the cautious reading described in the question.

This list is kept in step with the graph by `backend/tests/test_open_questions.py`.

## Cooling fan not operating (`cooling_fan_failure`)

- Does a fan that runs but is noisy count as faulty? The manual does not say, so 'noisy' leaves this cause inconclusive and investigation continues.
  - Depends on: ABB ACS580 firmware manual 3AXD50000016097 Rev J, Fault tracing: A581 Fan (printed p. 543); ABB service guidance on fan wear

## Ambient above derating temperature with load over derated capacity (`load_above_derated_capacity`)

- Which ambient limit applies to which frame? The 4290 text gives overlapping frame ranges (R4...R9 for 40 °C, R1...R9 for 50 °C), so no single temperature is encoded and 40-50 °C is treated as unclear.
  - Depends on: ACS580 hardware manual, chapter Technical data, section Derating
- Should this cause be ruled out when the ambient is unclear but the load is within the derated capacity? It is currently left inconclusive so later checks continue.
  - Depends on: ABB ACS580 firmware manual 3AXD50000016097 Rev J, Fault tracing: 4290 Cooling (printed p. 557); ACS580 hardware manual, section Derating
- Does a load over the derated capacity confirm this cause when the ambient is unclear (not known to be below the derating temperature)? It currently does.
  - Depends on: ABB ACS580 firmware manual 3AXD50000016097 Rev J, Fault tracing: 4290 Cooling (printed p. 557); ACS580 hardware manual, section Derating

## Motor power exceeds drive power (`motor_exceeds_drive_power`)

- What is the recommended corrective action for an undersized drive: resize the drive, derate, or reduce the load? The firmware manual gives no procedure.
  - Depends on: ABB ACS580 firmware manual 3AXD50000016097 Rev J, Fault tracing: 4210 IGBT overtemperature (printed p. 556); ACS580 hardware manual (drive sizing) or ABB guidance
