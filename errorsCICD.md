Run `npm run typecheck`

```text
> frontend@0.0.0 typecheck
> tsc -b --noEmit

Error: src/pages/Expediente.tsx(6,112): error TS6133: 'Download' is declared but its value is never read.
Error: Process completed with exit code 2.
```

Run `ruff check .`

```text
I001 [*] Import block is un-sorted or un-formatted
  --> alembic/versions/3a081d414e04_add_clerk_id_to_tenant.py:8:1

W293 [*] Blank line contains whitespace
  --> alembic/versions/3a081d414e04_add_clerk_id_to_tenant.py:24:1

I001 [*] Import block is un-sorted or un-formatted
  --> alembic/versions/bfe703abd33e_create_rds_pgaudit_role.py:8:1

F401 [*] `sqlalchemy` imported but unused
  --> alembic/versions/bfe703abd33e_create_rds_pgaudit_role.py:11:22

F401 [*] `io` imported but unused
  --> app/api/v1/expedientes.py:4:8

F401 [*] `fastapi.responses.StreamingResponse` imported but unused
  --> app/api/v1/expedientes.py:9:31

F401 [*] `app.models.nota.Nota` imported but unused
  --> app/api/v1/expedientes.py:16:29

W291 [*] Trailing whitespace
  --> app/api/v1/expedientes.py:84:33

E501 Line too long (148 > 100)
  --> app/api/v1/expedientes.py:85:101

E501 Line too long (109 > 100)
  --> app/api/v1/notas.py:37:101

I001 [*] Import block is un-sorted or un-formatted
  --> app/middleware/audit.py:16:1

F401 [*] `typing.Any` imported but unused
  --> app/middleware/audit.py:21:20

S110 `try`-`except`-`pass` detected, consider logging the exception
  --> app/services/encryption.py:79:9

I001 [*] Import block is un-sorted or un-formatted
  --> scripts/smoke_test.py:10:1

F401 [*] `app.core.config.settings` imported but unused
  --> scripts/smoke_test.py:10:29

F401 [*] `app.services.firma._sign_with_kms` imported but unused
  --> scripts/smoke_test.py:11:61

W293 [*] Blank line contains whitespace
  --> scripts/smoke_test.py:15:1

W293 [*] Blank line contains whitespace
  --> scripts/smoke_test.py:18:1

W293 [*] Blank line contains whitespace
  --> scripts/smoke_test.py:21:1

E501 Line too long (106 > 100)
  --> scripts/smoke_test.py:23:101

W293 [*] Blank line contains whitespace
  --> scripts/smoke_test.py:25:1

W293 [*] Blank line contains whitespace
  --> scripts/smoke_test.py:29:1

W293 [*] Blank line contains whitespace
  --> scripts/smoke_test.py:35:1

W291 [*] Trailing whitespace
  --> scripts/smoke_test.py:36:84

I001 [*] Import block is un-sorted or un-formatted
  --> scripts/smoke_test.py:39:9

W293 [*] Blank line contains whitespace
  --> scripts/smoke_test.py:42:1

W293 [*] Blank line contains whitespace
  --> scripts/smoke_test.py:51:1

W293 [*] Blank line contains whitespace
  --> scripts/smoke_test.py:57:1

W293 [*] Blank line contains whitespace
  --> scripts/smoke_test.py:67:1

W293 [*] Blank line contains whitespace
  --> scripts/smoke_test.py:75:1

W293 [*] Blank line contains whitespace
  --> scripts/smoke_test.py:80:1

W293 [*] Blank line contains whitespace
  --> scripts/upgrade_tenant.py:21:1

W293 [*] Blank line contains whitespace
  --> scripts/upgrade_tenant.py:25:1

E501 Line too long (108 > 100)
  --> scripts/upgrade_tenant.py:27:100

W293 [*] Blank line contains whitespace
  --> scripts/upgrade_tenant.py:31:1

W293 [*] Blank line contains whitespace
  --> scripts/upgrade_tenant.py:34:1

W293 [*] Blank line contains whitespace
  --> scripts/upgrade_tenant.py:42:1

W293 [*] Blank line contains whitespace
  --> scripts/upgrade_tenant.py:48:1

W293 [*] Blank line contains whitespace
  --> scripts/upgrade_tenant.py:51:1

W293 [*] Blank line contains whitespace
  --> scripts/upgrade_tenant.py:66:1

W293 [*] Blank line contains whitespace
  --> scripts/upgrade_tenant.py:72:1

E501 Line too long (136 > 100)
  --> scripts/upgrade_tenant.py:75:101

W293 [*] Blank line contains whitespace
  --> scripts/upgrade_tenant.py:83:1

I001 [*] Import block is un-sorted or un-formatted
  --> tests/integration/test_citas.py:1:1

F401 [*] `uuid.uuid4` imported but unused
  --> tests/integration/test_citas.py:4:18

E501 Line too long (123 > 100)
  --> tests/integration/test_citas.py:43:101

I001 [*] Import block is un-sorted or un-formatted
  --> tests/integration/test_expedientes.py:1:1

E501 Line too long (114 > 100)
  --> tests/integration/test_expedientes.py:40:101

W293 [*] Blank line contains whitespace
  --> tests/integration/test_expedientes.py:58:1

W293 [*] Blank line contains whitespace
  --> tests/integration/test_expedientes.py:69:1

I001 [*] Import block is un-sorted or un-formatted
  --> tests/integration/test_notas.py:1:1

W293 [*] Blank line contains whitespace
  --> tests/integration/test_notas.py:59:1

I001 [*] Import block is un-sorted or un-formatted
  --> tests/integration/test_pacientes.py:1:1

W293 [*] Blank line contains whitespace
  --> tests/integration/test_pacientes.py:51:1

F401 [*] `os` imported but unused
  --> tests/unit/test_services.py:1:8

W293 [*] Blank line contains whitespace
  --> tests/unit/test_services.py:42:1

Found 56 errors.
[*] 48 fixable with the `--fix` option.

Error: Process completed with exit code 1.
```

Run `aws lambda update-function-code`

```text
Error: aws: [ERROR]: An error occurred (ResourceNotFoundException) when calling the UpdateFunctionCode operation: Function not found: arn:aws:lambda:us-east-1:107759015501:function:medrecord-api-dev

Additional error details:
Type: User

Error: Process completed with exit code 254.
```