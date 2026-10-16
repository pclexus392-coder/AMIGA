# Proyek AMIGA tetap

Folder ini adalah workspace utama AMIGA. Kerjakan pembaruan **di tempat**, bukan membuat amiga-v3, amiga-final-baru atau salinan proyek setiap turn. Jangan membuat ZIP baru kecuali pengguna memintanya. Demo v1/v2 di folder lain adalah referensi/arsip.

## Kepemilikan pekerjaan

- Codex: frontend dan backend, tes, migrasi, launcher, dan dokumentasi. Pengguna menyerahkan pekerjaan Argon kepada Codex pada 15 Oktober 2026 setelah hasilnya diperiksa.
- Frontend mengikuti `AMIGA_KONTRAK_API.md`; perubahan yang diperlukan dicatat, bukan disamarkan. Simpan data lama, jangan mengimpor data tanpa pemilik ke tenant secara otomatis.

## Batas penting

- `/atmin` adalah permintaan aktivasi admin, bukan email/password/izin admin dengan sendirinya. Default login memakai password AMIGA (bcrypt) dan JWT cookie HttpOnly. Pemilik membuat password sendiri pada form melalui capability sekali pakai dari launcher lokal (CLI setup-admin tetap alternatif). Pengguna lain membuat password sendiri, admin hanya mengatur akses. Hak akses diverifikasi backend; Google hanya opsional.
- Pratinjau lokal harus diberi label simulasi. Mode backend tidak boleh diam-diam memakai data demo saat API gagal.
- SYSTEM_ADMIN tidak approve voucher. Finance Reviewer bukan uploader. Isolasi klien harus ada di backend.
- Daftar email biasa membuat CLIENT_OWNER dengan tenant baru yang privat. /review atau /view meminta Finance Reviewer (PENDING_REVIEWER), /atmin meminta admin; kedua permintaan internal tidak memberi role tanpa otorisasi. Setelah aktif, email biasa mengenali role tersimpan. Jangan membuka akses tenant existing melalui suffix.
- Ekstraksi invoice aktif memakai AWS Bedrock Nova Lite (apac.amazon.nova-lite-v1:0) dari ZIP utama. Pengaturan AWS diaktifkan selektif; jangan ganti database/auth dengan .env.source. Nova Lite maksimal 5.000 token, OCR per halaman; JSON/respons terpotong tidak boleh diterbitkan parsial. Tidak ada fallback provider otomatis. Analisis reviewer existing tetap OpenAI Luna terpisah dari AI_PROVIDER ekstraksi; tiga agent Luna dan Telegram opsional aktif (v4). Tes otomatis tidak memanggil API berbayar; uji manual PDF teks dan scan fiktif telah lulus. Lihat PERBAIKAN_EKSTRAKSI_INVOICE.md.
- Tidak ada deploy publik, email keluar, atau pembayaran tanpa instruksi pengguna.
- Alur tugas bersama menggantikan assignment klien per reviewer (permintaan pengguna 15 Oktober): /review tetap PENDING_REVIEWER, admin menyetujui satu kali tanpa client_ids. Portal reviewer terpisah di /reviewer. Reviewer aktif melihat ringkasan tugas terbuka lintas klien; detail/PDF/edit/AI hanya setelah mengambil tugas secara eksklusif. Klien tetap hanya mengakses tenant yang ditugaskan. Admin/Service Lead memantau seluruh pekerjaan dan dapat menugaskan ulang; admin tetap tidak approve voucher.
- Admin dapat menghentikan reviewer: cabut sesi, kembalikan tugas belum selesai ke antrean, pertahankan riwayat/voucher yang sudah disetujui. Revisi baru dengan PIC nonaktif kembali ke antrean. Analisis AI hanya saran: analisis awal uploader otomatis, asisten/analisis reviewer dipicu pengguna, memakai versi tersimpan dan PDF melalui API Luna; tidak mengedit atau approve. Jangan memanggil API berbayar dari tes otomatis.
- Pertahankan tema gelap/terang dan aksesibilitas reduced motion. Nilai finansial memakai decimal/integer minor units.
- Jalankan tes frontend dan build dari package.json setelah perubahan terkait. Catat batas verifikasi backend/Google/AWS apa adanya.

- Lifecycle v3: OPEN/CLOSED adalah penerimaan layanan administrasi oleh Klien/Backup, bukan pembayaran. CLOSE hanya setelah seluruh voucher aktif disetujui dan diunduh klien. REQUEST_REVISION pada hasil terbit/CLOSED membuat versi baru seluruh invoice, tanpa menimpa voucher lama. Semua mutation konten harus memeriksa require_open; unduhan/histori tetap tersedia. Kunci parent request dan cek revision lifecycle + seluruh versi invoice. Jangan menambah pengecualian per tombol yang melewati aturan ini.

- Tema AMIGA: logo perusahaan, teal/pink, terang + gelap. Tipografi hanya Newsreader dan Figtree lokal (SIL OFL); skala 1,25 dari base clamp 16–18px, weight 400/500/600. Semua deklarasi tipografi dipusatkan pada frontend/portal/src/css/typography.css, warna pada amiga-theme.css; jangan menambah font/ukuran/tracking acak ke stylesheet layout lama. Panduan: TIPOGRAFI_AMIGA.md, specimen /portal/typography.html. Data tabel memakai angka tabular dan scroll horizontal bila perlu.

- Pengguna menetapkan amiga-20261015T221710Z-1-001.zip sebagai backend utama pada 16 Oktober 2026. Entry point backend/app.py, controller backend/modules/{auth,admin,upload}/routes.py, queue_store/queue_worker dan voucher_service adalah implementasi aktif. backend/api.py serta processing.py hanya compatibility import; jangan menghidupkan backend paralel atau kembali ke renderer lama. Lihat INTEGRASI_BACKEND_UTAMA.md dan backend/source_manifest.json.
- Data ZIP di backend/storage/source-archive berstatus PRESERVED_UNASSIGNED. Jangan memetakan ID perusahaan/user PostgreSQL ke tenant lama dengan tebakan. backend/.env.source privat dan tidak otomatis menggantikan konfigurasi aktif. Tiga chatbot Luna dan Telegram opsional kini aktif melalui controller tambahan pada schema yang sama. PIC QC sebagai peran kelima terpisah tidak ditambahkan.

- Pendaftaran ditentukan hanya oleh akhiran email: /atmin untuk admin, /review atau /view untuk reviewer, tanpa akhiran untuk klien. Jangan tambahkan pemilih peran atau state frontend yang menimpa akhiran email.

- Perhitungan invoice: HALF_UP dua desimal per hasil baris dan total akhir; quantity/harga input sampai enam desimal. Selisih = hasil hitung dikurangi total PDF. Angka sumber tetap utuh; jangan menimpa angka PDF agar validasi lolos. Kontrak browser/server dibuktikan tests/fixtures/invoice_math.json.

- Panel progres enam tahap (Dokumen masuk sampai Ditutup) hanya ditampilkan di portal uploader/klien, bukan reviewer/admin. Reviewer tetap memakai status ringkas dan alur pemeriksaan/voucher; data lifecycle dan izin backend tetap berlaku.

- Progres uploader memiliki bilah ringkas sticky saat panel penuh melewati atas viewport (36px desktop, 40px mobile). Tetap dalam kolom konten, hormati reduced motion, dan bersihkan observer melalui releaseProgress saat route berubah. Jangan munculkan kembali di reviewer/admin.

- Workflow v4: setelah ekstraksi Nova, worker menjalankan analisis awal Luna. Uploader harus mengonfirmasi tiap versi/fingerprint dan seluruh item sebelum tugas tersedia/claim/assignment/approve. Edit data atau bukti membatalkan konfirmasi; reviewer tetap independen.
- Uploader dapat mengganti PDF/foto pada Request ID yang sama saat OPEN/idle. Pertahankan seluruh dokumen, ekstraksi, review dan voucher lama. Jika ada voucher aktif terbit, wajib persetujuan eksplisit supersede_published; voucher menjadi arsip, bukan ditimpa. Arsip hanya diunduh melalui endpoint scoped dan tidak dihitung handover aktif. CLOSED tetap harus dibuka melalui lifecycle dahulu.
- Tiga asisten memakai AGENT_MODEL=gpt-6-luna; jangan mengganti ke Sol. Konteks/rate limit/kuota dikendalikan server, metrik reviewer hanya admin/service lead. AI tidak mengeksekusi perubahan izin, approval, atau pembayaran.
- Telegram opsional dan tidak memblokir login. Pengiriman reviewer memerlukan percakapan terbaru, pratinjau penerima/isi/versi/lampiran dan persetujuan eksplisit. Timeout UNKNOWN tidak boleh auto-retry. Uji otomatis memakai transport fiktif dan tidak boleh mengirim pesan nyata.
- Dokumentasi terbaru: API_TERBARU.md dan PARTNER_REVIEW.md. Prepare-PartnerReview.ps1 mengemas source/contoh konfigurasi; kunci API asli, .env privat, database dan dokumen klien tidak boleh masuk paket. Jangan buat ZIP sampai diminta.

- Asisten utama kini bubble non-modal Tanya AMIGA. UI percakapan tetap satu implementasi agent-page.js dengan root scoped; assistant-bubble.js menampilkannya sebagai panel, tanpa backend/permission baru. Draft dalam memori per konteks, bersihkan widget dan listener saat logout/pergantian akun; hindari duplikasi ID saat halaman asisten penuh terbuka. Telegram tetap memerlukan pratinjau dan persetujuan.

- Menu Asisten AI di sidebar dihapus untuk semua peran atas permintaan pengguna. Gunakan bubble Tanya AMIGA; halaman penuh tetap dapat dibuka lewat tombol perluas pada bubble.

- Target deployment EC2 Kelompok 10: port publik 80 via Nginx, Gunicorn hanya 127.0.0.1:3000. Backend/deployment.py menjaga produksi/PostgreSQL/cookie Secure dan penggunaan instance role. Jangan menyalin .env AWS laptop atau data klien ke GitHub/EC2. Repo privat pengguna: pclexus392-coder/AMIGA. Akses AWS lab/instance/HTTPS masih perlu diverifikasi; jangan menyebut aplikasi sudah live hanya karena source/paket telah siap.
