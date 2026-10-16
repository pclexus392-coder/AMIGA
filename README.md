# AMIGA - proyek utama tetap

Backend utama sekarang berasal dari **amiga-20261015T221710Z-1-001.zip** (16 Oktober 2026), diadaptasi ke portal yang sudah dibuat. Ringkasan struktur, data arsip dan batas koneksi ada di [INTEGRASI_BACKEND_UTAMA.md](INTEGRASI_BACKEND_UTAMA.md). Jalankan launcher yang sama; bukan project/server baru.

Panduan penggunaan: [Cara kerja AMIGA](CARA_KERJA_AMIGA.md). Alur terbaru: unggah → ekstraksi Nova → analisis awal Luna → konfirmasi uploader → reviewer mengambil tugas → voucher. Tiga asisten Luna, revisi dokumen dan Telegram opsional dijelaskan pada [API terbaru](API_TERBARU.md). Untuk partner: [panduan review](PARTNER_REVIEW.md).

Backend dan frontend sekarang dikerjakan Codex di folder ini. Proyek lama dan data legacy tidak dihapus. Tidak ada folder versi baru atau ZIP tambahan.

## Menjalankan aplikasi

- **Start-AMIGA.cmd** (atau **Start-Backend.cmd**): backend Flask dan portal Klien, Reviewer dan Admin pada http://127.0.0.1:5000/login. Dependency lokal sudah dipasang pada `.venv` dalam workspace ini.
- **Setup-Backend.cmd**: pemasangan dependency pertama kali di komputer lain (Python 3.12+ dan internet), lalu inisialisasi database pengembangan SQLite.
- **Start-AMIGA.cmd preview**: pratinjau frontend terpisah pada http://127.0.0.1:4175/login, memakai data fiktif dan tanpa login Google. Launcher ini dipertahankan agar alur pratinjau sebelumnya tetap tersedia.

Biarkan terminal terbuka selama aplikasi digunakan; Ctrl+C untuk berhenti. `Start-Backend.cmd` hanya membuka port loopback. Ini server pengembangan lokal.

## Login tanpa Google dan aktivasi admin pertama

Metode mengikuti materi Session 08 Teaching KelanaAI to Know Its Users: daftar, login email/password, bcrypt, JWT, endpoint terlindungi dan kepemilikan data dari server. Stack Flask yang sudah ada dipertahankan. `AUTH_METHOD=local_password` menjadi default; Google Cloud dan GOOGLE_CLIENT_ID tidak diperlukan untuk login ini.

1. Tutup terminal server AMIGA lama dengan Ctrl+C, lalu jalankan **Start-AMIGA.cmd**. Launcher membuka browser setelah server yang baru siap. Jika akun pemilik belum dibuat, browser menampilkan **Siapkan akun pemilik** dengan email `/atmin` yang sudah diisi.
2. Isi nama, buat password AMIGA sendiri, dan ulangi password pada formulir tersebut. Minimal 10 karakter, maksimal 72 byte UTF-8. Klik **Buat password & aktifkan** untuk masuk sebagai admin pertama. Password tidak perlu dimasukkan ke terminal atau Google.
3. Login berikutnya cukup email biasa dan password AMIGA. Peluncuran berikutnya tidak meminta setup password lagi. Sesi tetap berlaku selama 8 jam secara default, termasuk saat halaman dimuat ulang.
4. Pengguna lain memilih **Belum punya akun? Daftar** pada form yang sama. Email tanpa akhiran membuat akun CLIENT_OWNER aktif dengan workspace klien pribadi yang baru. Email /review meminta peran Finance Reviewer (PENDING_REVIEWER), dan /atmin meminta admin (PENDING_ADMIN). Kedua permintaan internal menunggu persetujuan admin satu kali; reviewer tidak memerlukan assignment klien; suffix tidak memberikan izin dengan sendirinya. Email adalah ID akun lokal, bukan klaim bahwa kepemilikan Gmail sudah diverifikasi. Tidak ada email atau OTP yang dikirim. Pengelola memeriksa identitas dan menetapkan akses secara manual.
5. Pada **Reviewer & akun**, admin cukup menekan **Setujui reviewer** untuk mengaktifkan permintaan /review. **Nonaktifkan reviewer** mencabut sesi dan mengembalikan tugas belum selesai ke antrean. Assignment klien hanya diperlukan bagi Klien/Backup. Perubahan akses mencabut sesi akun terkait. System Admin tidak dapat approve invoice atau mengubah akses dirinya sendiri melalui API.

Password disimpan sebagai bcrypt salted hash (cost 12). JWT HS256 memuat sub/iat/exp/jti/iss/aud dan diverifikasi pada setiap request. JWT berada dalam cookie HttpOnly, SameSite=Lax (Secure pada produksi), tidak di localStorage. Database hanya menyimpan hash token untuk pencabutan sesi saat logout atau perubahan akses. Semua mutasi tetap memerlukan CSRF. Lima password salah mengunci akun 15 menit. `/atmin` dan email allowlist saja tidak cukup untuk mengaktifkan admin melalui pendaftaran publik.

Allowlist pemilik sudah dikonfigurasi di backend/.env privat. Password nyata belum dibuat oleh Codex; pemilik membuatnya sendiri pada formulir. Ekstraksi invoice memakai AWS Bedrock Nova Lite. Analisis awal dan tiga asisten memakai OpenAI GPT-6 Luna, dengan OPENAI_API_KEY_FILE menunjuk sumber kunci yang sama dengan Atlas. Nilai kunci tidak disalin ke frontend atau contoh konfigurasi. Login tidak bergantung pada layanan AI tersebut.

Aktivasi pertama memakai tautan lokal sekali pakai, berlaku 30 menit, yang hanya dibuat launcher lokal. Database menyimpan hash kodenya. Kode pada fragmen URL langsung dihapus dari address bar dan setelah diverifikasi disimpan dalam cookie HttpOnly agar refresh tidak menghilangkan formulir. Pendaftaran yang berhasil menghabiskan kode secara atomik. Kode salah, kedaluwarsa, email lain dan pemakaian ulang ditolak. Tidak ada kode aktivasi di localStorage atau log URL server. Menjalankan ulang launcher sebelum aktivasi mengganti tautan lama.

Launcher lokal memakai reloader sumber Python dengan debugger tetap mati dan satu worker pada proses pelayan. HTML/JS/CSS pengembangan tidak dicache. Bila server lama tidak mengirim auth_method yang dikenal, halaman menghentikan login dengan petunjuk restart; tidak menebak atau beralih ke Google. Launcher menolak port yang sedang dipakai dan tidak menghentikan proses lain. CLI `setup-admin` lama tetap tersedia sebagai alternatif operator dengan input password tersembunyi, tetapi tidak dipanggil oleh launcher default.

## PostgreSQL dan file konfigurasi yang ditunjukkan pengguna

File `C:/Users/Gerardus Theo P.S/Documents/HOBBY/amiga-main/amiga-main/backend/API/.env` sudah diperiksa tanpa menampilkan atau menyalin rahasia. File tersebut hanya berisi DATABASE_URL PostgreSQL lokal. Uji koneksi hanya-baca dari lingkungan Codex timeout; belum ada DDL atau perubahan data pada database itu.

Untuk pengembangan saat ini, DATABASE_URL kosong memakai SQLite lokal `backend/storage/amiga.db`. PostgreSQL didukung oleh SQLAlchemy/psycopg, tetapi belum diuji pada server nyata. Periksa `migrations/001_workspace.sql`, `002_local_auth.sql`, dan `003_request_lifecycle.sql` sebelum inisialisasi PostgreSQL. SQLite menambahkan tabel yang belum ada dan menaikkan versi skema 1/2 ke 3 tanpa menghapus data. PostgreSQL memerlukan migrasi 002 lalu 003 sesuai versi awal; server biasa menolak versi lama.

Perintah operator berikut **menambahkan tabel** `amiga_*`; jalankan hanya setelah menyetujui migrasi dan membuat backup database asli:

```powershell
.\.venv\Scripts\python.exe -m backend.manage --env-file "C:/Users/Gerardus Theo P.S/Documents/HOBBY/amiga-main/amiga-main/backend/API/.env" init-db
```

Opsi `--env-file` membaca file yang ada tanpa menyalin password. Untuk menjalankan dengan file itu, ganti `init-db` dengan `serve` setelah skema siap. Variabel environment proses mendapat prioritas atas isi file. Kredensial AWS hanya diperlukan bila memilih provider Bedrock; Luna memakai kunci OpenAI server; tidak ada penemuan kredensial otomatis dari direktori lain.

Tabel lama `queue_items` dan `invoice_records` tetap utuh. Data lama tanpa tenant tidak otomatis terlihat pada portal baru. Rekonsiliasi pemilik dan impor legacy perlu dikerjakan secara eksplisit. Struktur relasional dan alasan normalisasi ada di `SCHEMA_3NF.md`.

## Alur kerja backend

Papan tugas diperbarui otomatis delapan detik pada halaman aktif. Asisten analisis Luna dapat dipicu reviewer setelah menyimpan draft; hasil tersimpan di audit dan tidak mengubah data atau keputusan review.


1. Akun klien atau Finance Reviewer mengunggah PDF asli dan bukti untuk klien yang ditugaskan. Maksimal 10 MB dan 5 halaman per PDF; bukti maksimal 10 file dan total request 32 MB.
2. Worker menyimpan antrean di database. Ekstraksi default memakai GPT-6 Luna melalui OpenAI Responses API. PDF dikirim sebagai input_file base64 dengan detail high, output JSON Schema strict, dan store=false. Seluruh halaman, item dan transkripsi dipertahankan untuk review. Bedrock tetap opsional dengan AI_PROVIDER=bedrock, BEDROCK_MODEL_ID dan kredensial AWS; tidak ada perpindahan provider otomatis saat gagal. Semua invoice dari dokumen dipertahankan. Hasil yang terpotong/gagal menjadi EXCEPTION, bukan hasil palsu.
3. Pemrosesan menyimpan hasil ekstraksi asli secara append-only. Pengguna membandingkan semua item dengan PDF, mengonfirmasi jumlahnya, lalu menyimpan revisi dengan alasan. Rekening yang berubah memerlukan sumber bukti milik request yang sama.
4. Perhitungan server menggunakan Decimal: jumlah × harga - diskon + pajak item; jumlah seluruh item - diskon invoice + pajak invoice. Nilai unknown tetap null dan memblokir approval. Toleransi IDR 1 dan mata uang lain 0.01 masih aturan awal yang perlu disetujui pemilik proses.
5. Validasi ulang tidak memanggil AI. File identik atau vendor/nomor sama dalam tenant diblokir sampai reviewer memberi resolusi beralasan; flag tetap tersimpan dalam validasi dan audit. Versi baru membatalkan resolusi lama.
6. Finance Reviewer harus aktif, independen dari seluruh pengunggah invoice/bukti, dan mengambil tugas terlebih dahulu. Papan bersama menampilkan ringkasan semua klien tanpa assignment per klien; detail/PDF/edit hanya bagi reviewer pemilik tugas. Admin/Service Lead dapat memilih ulang PIC melalui detail request yang belum selesai. System Admin tetap tidak bisa approve, termasuk jika data perannya keliru digabung dengan reviewer.
7. Approval membuat snapshot validasi dan PDF resmi tetap. Preview belum approve berwatermark DRAFT. Revisi berikutnya memerlukan approval baru. Approval pada versi lama ditolak dengan 409.
8. Menu **Voucher reviewer** menyediakan pusat penerbitan: pilih draft, periksa data, konfirmasi, terbitkan.
9. Unduhan resmi Klien/Backup mencatat penyerahan melalui browser, bukan email atau pembayaran. Unduhan internal reviewer/admin tidak mencatat handover. Request multi-invoice menjadi SENT_TO_CLIENT setelah setiap voucher invoice aktif diunduh oleh Klien/Backup yang berwenang.

10. Klien menutup pekerjaan setelah seluruh voucher terbaru diunduh. CLOSED mengunci perubahan; klien dapat meminta revisi beralasan yang membuka kembali pekerjaan dan membuat versi baru untuk review independen. Status pembayaran tetap di luar AMIGA.

Penyimpanan dokumen saat ini privat di disk lokal dan PDF resmi berada di database. API selalu memeriksa tenant; route lama yang menampilkan antrean/dokumen tanpa auth tidak didaftarkan. Penyimpanan S3, antivirus, backup operasional, deployment HTTPS/WSGI dan pemantauan produksi belum dikonfigurasi. Tidak ada deploy publik atau pembayaran.

## Provisioning operator lokal

Penetapan role/assignment oleh pemilik komputer, setelah pengguna mendaftar dengan password melalui aplikasi:

```powershell
.\.venv\Scripts\python.exe -m backend.manage create-client --name "Nama klien sebenarnya"
.\.venv\Scripts\python.exe -m backend.manage provision-user --email "reviewer@domain-anda.com" --role FINANCE_REVIEWER
```

CLI ini menambah role/assignment; bukan menghapus role lama. Tidak mengirim email. Untuk mengubah/mencabut akses gunakan API/halaman akun. Jangan memakai email ilustrasi sebagai akun nyata.

## Verifikasi

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests/backend -v
node --test --test-isolation=none frontend/tests/domain.test.mjs frontend/tests/analytics.test.mjs frontend/tests/portal.test.mjs
node frontend/scripts/build.mjs
```

Lihat `INTEGRATION_STATUS.md` untuk jumlah hasil final dan batas pengujian. Login lokal diuji menggunakan bcrypt/JWT sebenarnya pada database sementara. Jalur Google opsional memakai klaim/sertifikat uji, ekstraksi memakai fixture. Itu tidak membuktikan Google/AWS atau PostgreSQL asli sudah terhubung.

Tes browser opsional `frontend/tests/browser-integration.mjs` membutuhkan Playwright dan Chrome/Chromium. Set `AMIGA_BROWSER_AUTH=local_password` untuk alur bcrypt/JWT sebenarnya tanpa Google; tanpa variabel ini, tes menjalankan jalur Google fixture. Karena sandbox menolak koneksi loopback, tes memakai bridge WSGI melalui stdio pada database sementara. Ekstraksi memakai fixture. Bridge tidak terdaftar dalam server biasa. Screenshot QA berada di `.runtime-temp/browser-qa/`.

## Struktur tetap

- `backend/application.py`, `api.py`: factory, sesi, auth, API berizin dan portal satu origin.
- `backend/models.py`, `repository.py`, `validation.py`: tabel, versi immutable, sumber, Decimal dan validasi.
- `backend/processing.py`, `pdf_service.py`: antrean dengan lease/fencing, Bedrock, dan PDF voucher.
- `backend/manage.py`, `schema.py`, `.env.example`, `requirements.txt`: pengaturan lokal dan migrasi.
- `frontend/portal/`: tiga portal dark/light, diagram dan animasi reduced motion.
- `frontend/scripts/`, `frontend/tests/`, `tests/backend/`, `migrations/`: build dan verifikasi.
- `backend/modules/upload/`, `backend/voucher_service.py`, `frontend/templates/`: referensi source lama; handler HTTP lamanya tidak aktif.

## Penyelesaian konfigurasi (15 Oktober 2026)

Start-AMIGA.cmd kini membuka aplikasi lengkap pada port 5000. Start-Backend.cmd tetap menjadi alias launcher backend. Untuk preview Node lama gunakan Start-AMIGA.cmd preview. Check-AMIGA.cmd memeriksa keberadaan konfigurasi tanpa melakukan koneksi database/cloud atau mencetak nilai rahasia.

Google OAuth opsional, hanya bila AUTH_METHOD diubah menjadi google. Lewati bagian ini untuk login default email/password:

1. Buka [Clients pada Google Auth Platform](https://console.cloud.google.com/auth/clients), lalu pilih proyek milikmu.
2. Buat atau pilih OAuth client bertipe Web application. Atur branding/consent aplikasi sesuai akun Google yang digunakan.
3. Daftarkan http://localhost dan http://localhost:5000 pada Authorized JavaScript origins. Gunakan http://localhost:5000/login untuk alur ini. Bila memakai origin lain, daftarkan origin tersebut juga.
4. Salin Client ID (berakhiran .apps.googleusercontent.com) ke GOOGLE_CLIENT_ID di backend/.env. Flow ini memakai callback JavaScript dan verifikasi ID token; jangan memasukkan client secret ke frontend atau percakapan.
5. Jalankan ulang Start-AMIGA.cmd. Ketik Gmail pemilik dengan /atmin pada halaman login yang sama, kemudian verifikasi akun Google yang sama. Setelah aktif, login berikutnya memakai email normal.

Petunjuk origin, consent, dan client ID mengikuti [dokumentasi resmi Google Identity Services](https://developers.google.com/identity/gsi/web/guides/get-google-api-clientid). Header referrer pada mode lokal dan kebijakan popup aplikasi sudah disesuaikan untuk login Google.

AWS/Bedrock opsional (AI_PROVIDER=bedrock): isi BEDROCK_MODEL_ID dan region model yang memang tersedia pada akunmu. Siapkan kredensial melalui provider chain boto3, misalnya profil AWS yang sesuai; jangan mengirim secret key melalui percakapan. Rujukan: [dokumentasi credentials boto3](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/credentials.html). Pemeriksaan offline hanya mengenali petunjuk provider; itu bukan bukti autentikasi atau izin model berhasil. Sampai aktivasi ini dilakukan, jangan menganggap hasil demo sebagai ekstraksi AI nyata.

Konfigurasi admin pemilik disimpan hanya di backend/.env yang diabaikan Git; tidak disalin ke file contoh. Database PostgreSQL asli tetap belum disentuh. Hasil verifikasi terbaru dicatat pada INTEGRATION_STATUS.md.

## Halaman masuk tunggal

Login utama memiliki satu form email dan password AMIGA. Pendaftaran memakai form yang sama melalui tombol Daftar. Tidak ada tombol backend, pemilih mode, atau daftar akun contoh. Saat pengguna mengetik email dengan akhiran /atmin, penanda Aktivasi admin muncul. Izin admin tetap diperiksa server setelah password benar. Admin yang sudah aktif cukup memakai email biasa.

Pilihan mode lama dalam localStorage dan parameter URL tidak mengubah login utama menjadi demo. Preview pengembangan dipilih dari launcher Start-AMIGA.cmd preview dan diberi label simulasi; server preview menyisipkan penanda khusus pada HTML. Jika proxy AMIGA_API_ORIGIN diatur, server frontend tetap memakai API nyata. Kegagalan layanan tidak beralih ke demo.

Bukti visual login baru: .runtime-temp/browser-qa/login-card-dark.png, login-card-light.png, login-admin-trigger-dark.png. Pengujian browser mencakup suffix tanpa kewenangan tetap pending, login klien, admin aktif tanpa suffix, preferensi demo lama yang diabaikan, serta pesan layanan belum tersedia tanpa menampilkan konfigurasi teknis.

## Ekstraksi AWS Nova dan penanda /review

Ekstraksi instalasi ini aktif memakai AI_PROVIDER=bedrock, BEDROCK_MODEL_ID=apac.amazon.nova-lite-v1:0 dan region ap-southeast-1 dari konfigurasi ZIP utama. PDF teks dan scan fiktif telah lolos uji AWS nyata. Analisis reviewer existing tetap memakai OpenAI Luna melalui konfigurasi server yang terpisah; tiga agent GPT Sol belum diimplementasikan. Tidak ada fallback provider otomatis. Rincian perbaikan dan batas verifikasi: [PERBAIKAN_EKSTRAKSI_INVOICE.md](PERBAIKAN_EKSTRAKSI_INVOICE.md).

Uji API nyata dengan satu PDF fiktif berhasil: 1 invoice/1 item, total IDR 100000, validasi lolos dan rekening 0000123 tetap utuh. Ini uji sambungan dan format, bukan jaminan akurasi semua dokumen. Pemeriksaan manusia dan validasi Decimal tetap wajib. Perintah `python -m backend.manage check-ai` mengulang uji ini dan memakai kuota API berbayar. Pengujian unit/browser tetap memakai transport/extractor fixture dan tidak menghabiskan kuota.

Akun baru email biasa mendapat workspace pribadi yang terpisah dari semua klien existing. Permintaan /review terlihat pada Akun & akses; admin menyetujui reviewer satu kali tanpa assignment klien. Role yang sudah disetujui dikenali ketika login ulang dengan email biasa. Akun klien yang sudah aktif tidak naik role hanya dengan menambahkan /review atau /atmin; permintaan tanpa peran yang sesuai ditolak, dan admin perlu mengubah aksesnya. Akun pending existing tidak otomatis diaktifkan, serta akun disabled tidak dapat mendaftar ulang untuk melewati pembatasan.

Rujukan implementasi: [GPT-6 Luna](https://developers.openai.com/api/docs/models/gpt-6-luna), [PDF file inputs](https://developers.openai.com/api/docs/guides/file-inputs), [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses).


## Tema dan sistem tipografi AMIGA

Portal menggunakan logo AMIGA, teal/pink, mode terang/gelap, Newsreader + Figtree yang disimpan lokal. Baca `TIPOGRAFI_AMIGA.md` untuk pairing, token, CSS, contoh HTML dan lima aturan tim. Halaman `/portal/typography.html` memperlihatkan hierarki dan contoh angka. CSS tipografi dipusatkan pada `frontend/portal/src/css/typography.css`, warna/layout tema pada `amiga-theme.css`.

Pendaftaran menggunakan akhiran email tanpa kartu pilihan peran: `/review` atau `/view` untuk reviewer, `/atmin` untuk admin, email biasa untuk klien.

## Deployment EC2 Kelompok 10

Konfigurasi server dan panduan ada di [DEPLOY_EC2.md](DEPLOY_EC2.md). Port publik **80 melalui Nginx**; backend hanya localhost:3000, PostgreSQL lokal dan AWS memakai instance role. Deployment belum dijalankan sampai akun lab, instance tujuan serta endpoint HTTPS terverifikasi. Tidak ada kredensial/data klien di repo.
