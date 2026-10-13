# SDP Cloud CMDB to Microsoft Sentinel MVP

Collector minimal untuk:

1. meminta access token Zoho memakai refresh token;
2. mengambil CI dari `ci_computer` ServiceDesk Plus Cloud;
3. melakukan paging dan validasi jumlah data;
4. memetakan field aset inti;
5. mengirim snapshot ke satu stream Logs Ingestion API Microsoft Sentinel;
6. menyediakan Azure Function Timer Trigger untuk sync terjadwal per jam.

MVP ini belum mencakup run-log table, workbook, atau KQL function. Template DCR
serta custom table minimal tersedia di folder `infra`.

## Prasyarat Sentinel

Sebelum menjalankan mode `--send`, siapkan:

- custom table tujuan, misalnya `SDP_CMDB_Asset_CL`;
- Data Collection Rule (DCR) dengan custom stream yang sama persis dengan
  `streamDeclarations` pada JSON DCR. Template Bicep memakai
  `Custom-SDP_CMDB_Asset`; table wizard Portal dapat memakai
  `Custom-SDP_CMDB_Asset_CL`;
- DCR stream yang memetakan kolom berikut:

  `TimeGenerated`, `RunId`, `CiId`, `CiType`, `CiName`, `Description`,
  `HostnameNorm`, `IpAddress`, `OsName`, `Site`, `Criticality`, `CiStatus`,
  `SourceCreatedTime`, `SourceLastUpdated`, `RowHash`, `RawAttributes`;

- ingestion endpoint DCR;
- immutable ID DCR;
- identity yang menjalankan collector dengan role `Monitoring Metrics Publisher`
  pada DCR;
- Azure credential. Collector memakai `ClientSecretCredential` jika
  `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, dan `AZURE_CLIENT_SECRET` diisi;
  jika tidak, collector memakai `DefaultAzureCredential`.

### Provisioning cepat dengan Bicep

Template `infra\main.bicep` membuat:

- tabel `SDP_CMDB_Asset_CL` dengan plan Analytics;
- DCR direct ingestion;
- stream `Custom-SDP_CMDB_Asset`;
- data flow ke workspace Sentinel;
- optional role assignment `Monitoring Metrics Publisher` jika
  `collectorPrincipalId` diisi.

Salin parameter contoh dan isi resource group, subscription, serta region:

```powershell
Copy-Item infra\parameters.example.json infra\parameters.json
```

Deploy dari Azure CLI:

```powershell
az deployment group create `
  --resource-group <collector-resource-group> `
  --template-file infra\main.bicep `
  --parameters @infra\parameters.json
```

DCR direct menghasilkan ingestion endpoint dan immutable ID setelah dibuat.
Untuk DCR yang dikaitkan ke Data Collection Endpoint (DCE), gunakan nilai
`properties.logsIngestion.endpoint` dari JSON DCE sebagai endpoint. Ambil
immutable ID dari JSON DCR, lalu isi:

```text
AZURE_DCR_ENDPOINT=<DCR logs ingestion endpoint>
AZURE_DCR_IMMUTABLE_ID=<DCR immutable ID>
AZURE_DCR_STREAM_NAME=<exact streamDeclarations key>
```

Jika deployment dijalankan pada resource group yang berbeda dari workspace,
`workspaceResourceGroupName` dan `workspaceSubscriptionId` tetap harus
menunjuk ke workspace Sentinel yang sudah ada.

`RawAttributes` sebaiknya dibuat sebagai kolom `dynamic`. Pastikan transformasi
DCR mengarahkan `TimeGenerated` menjadi kolom waktu utama.

## Instalasi PowerShell

Dari folder proyek:

```powershell
Set-Location 'C:\Users\ACER\Documents\office\sdp-cmdb-sentinel-mvp'
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
```

Isi `.env` dengan credential SDP dan konfigurasi DCR. Jangan commit `.env`.

Untuk autentikasi berbasis service principal, isi tiga variable berikut di
`.env`. Gunakan **Application (client) ID**, **Directory (tenant) ID**, dan
**secret Value** (bukan Secret ID):

```text
AZURE_TENANT_ID=<Directory tenant ID>
AZURE_CLIENT_ID=<Application client ID>
AZURE_CLIENT_SECRET=<secret Value>
```

Service principal tersebut harus memiliki role `Monitoring Metrics Publisher`
pada DCR. Jangan commit `.env` atau membagikan nilai secret.

Jika ketiga variable tersebut kosong, collector memakai `DefaultAzureCredential`
sehingga dapat memakai Azure CLI, login VS Code, atau managed identity.

## Uji koneksi SDP tanpa mengirim ke Sentinel

Gunakan limit kecil terlebih dahulu:

```powershell
.\.venv\Scripts\python.exe -m sdp_sentinel_mvp --dry-run --limit 5
```

Hasilnya ditulis ke `data\assets-latest.json`. File tersebut di-ignore oleh Git.

## Kirim ke Sentinel

Setelah DCR dan Azure credential siap:

```powershell
.\.venv\Scripts\python.exe -m sdp_sentinel_mvp --send
```

Untuk menguji satu record terlebih dahulu:

```powershell
.\.venv\Scripts\python.exe -m sdp_sentinel_mvp --send --limit 1
```

CLI default tidak mengirim data jika `--send` tidak diberikan.

## Deploy otomatis dengan Azure Functions

`function_app.py` memakai Python programming model v2 dan menjalankan sync pada
menit 00 setiap jam dengan schedule `0 0 * * * *` (UTC). Logic pengambilan dan
transformasi dipakai bersama oleh CLI dan Function melalui
`src\sdp_sentinel_mvp\service.py`.

Buat Function App dengan:

- runtime **Python 3.11 atau 3.12**;
- Functions runtime **4**;
- region yang sesuai kebijakan organisasi;
- storage account yang dikelola oleh Function App;
- Application Insights untuk memantau execution dan error.

Jangan menaruh secret di source code atau `.env` saat deploy. Pada Function App,
buka **Settings → Environment variables → App settings**, lalu isi semua
variable pada tabel di bawah, termasuk:

```text
SDP_TOKEN_URL
SDP_API_BASE_URL
SDP_CI_TYPE
SDP_CLIENT_ID
SDP_CLIENT_SECRET
SDP_REFRESH_TOKEN
AZURE_DCR_ENDPOINT
AZURE_DCR_IMMUTABLE_ID
AZURE_DCR_STREAM_NAME
AZURE_TENANT_ID
AZURE_CLIENT_ID
AZURE_CLIENT_SECRET
```

`AZURE_CLIENT_ID` dan `AZURE_CLIENT_SECRET` adalah milik service principal yang
memiliki role `Monitoring Metrics Publisher` pada DCR. Azure menyimpan app
settings secara terenkripsi dan perubahan settings akan me-restart Function
App.

Deploy project dari VS Code menggunakan extension **Azure Functions**. Pilih
folder project ini sebagai workspace, pilih **Deploy to Function App**, lalu
pilih Function App yang sudah dibuat. File `.funcignore` mengecualikan `.env`,
virtual environment, cache, data lokal, dan test dari deployment.

## Konfigurasi utama

| Variable | Keterangan |
|---|---|
| `SDP_TOKEN_URL` | Endpoint refresh token Zoho |
| `SDP_API_BASE_URL` | `https://sdpondemand.manageengine.com/api/v3` |
| `SDP_CI_TYPE` | `ci_computer` |
| `SDP_CLIENT_ID` | Zoho Self Client ID |
| `SDP_CLIENT_SECRET` | Zoho Self Client secret |
| `SDP_REFRESH_TOKEN` | Zoho refresh token |
| `SDP_IP_FIELD_KEY` | Default `txt_ip_address` |
| `SDP_OS_FIELD_KEY` | Field key OS, opsional |
| `SDP_SITE_FIELD_KEY` | Default `txt_location` |
| `SDP_CRITICALITY_FIELD_KEY` | Default `ref_business_impact` |
| `AZURE_DCR_ENDPOINT` | Ingestion endpoint DCR |
| `AZURE_DCR_IMMUTABLE_ID` | Immutable ID DCR |
| `AZURE_DCR_STREAM_NAME` | Key `streamDeclarations` yang tepat pada DCR |
| `AZURE_TENANT_ID` | Directory (tenant) ID service principal, opsional |
| `AZURE_CLIENT_ID` | Application (client) ID service principal, opsional |
| `AZURE_CLIENT_SECRET` | Secret Value service principal, opsional dan sensitif |

## Catatan MVP

- Satu CI type (`ci_computer`) dan satu stream Sentinel.
- Snapshot penuh dikirim setiap eksekusi.
- Azure Function berjalan setiap jam pada menit 00 UTC.
- Access token tidak disimpan.
- Credential tidak ditulis ke log.
- Nilai field OS dan site dapat berbeda antar-tenant, sehingga field key-nya
  harus dikonfigurasi setelah response API diperiksa.
- Credential yang pernah dibagikan di luar lingkungan aman sebaiknya segera
  dirotasi.
