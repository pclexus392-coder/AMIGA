# Deployment AMIGA ke EC2 — Kelompok 10

Status: konfigurasi deployment disiapkan lokal. Belum ada EC2/IP/URL live yang diverifikasi. Akun lab, region sebenarnya, tag Owner, endpoint HTTPS dan izin Nova Lite harus diperiksa sebelum menjalankan perintah di server.

## Sesuai panduan mentor

PDF `Deploy aplikasi ke EC2.pdf` menetapkan satu instance dari `main-ec2-templates`, tanpa mengganti ukuran instance/disk/key pair. Owner harus username IAM persis, bukan otomatis nama kelompok. Akses melalui Session Manager, kemudian `sudo su - ec2-user` dan `cloud-init status --wait`. Tidak ada SSH key atau access key baru yang diperlukan. Jangan hentikan instance/server milik kelompok lain.

Konfigurasi EC2 disiapkan untuk `us-east-1`, port publik **80 melalui Nginx**, backend internal `127.0.0.1:3000`, PostgreSQL lokal dan kredensial AWS melalui instance role. Jangan salin `backend/.env`, `.env.source`, `C:\API`, database laptop atau dokumen pengguna ke repo/server.

Nova Lite tetap diperlukan untuk PDF scan/foto. Contoh Nova Micro dalam PDF mentor hanya mendukung teks; jangan mengganti model OCR ke Micro. Profil yang disiapkan adalah `us.amazon.nova-lite-v1:0`; akses role lab ke profil dan model tujuannya belum diuji. Jika role hanya mengizinkan Micro, minta mentor memeriksa akses Lite, bukan memasukkan access key lokal sebagai jalan pintas.

## Port publik 80 dan login produksi

Permintaan terbaru pengguna mengganti alamat publik menjadi `http://IP` (port 80). Nginx meneruskan trafik ke backend localhost:3000; port 3000 tidak perlu dibuka di security group. PDF mentor sebelumnya memakai port 3000. Login produksi AMIGA memakai cookie Secure dan membutuhkan endpoint HTTPS. Konfigurasi ini mempertahankan pengamanan tersebut: belum boleh dianggap siap login hanya karena `/health` pada HTTP membalas 200.

Gunakan ingress/reverse proxy HTTPS yang disediakan mentor, atau domain dan sertifikat valid pada konfigurasi yang disepakati. Untuk ingress HTTPS yang meneruskan ke Nginx port 80, batasi origin sesuai jalur ingress yang benar. Tidak ada penambahan port, DNS, load balancer, sertifikat atau biaya AWS yang dilakukan otomatis oleh file ini. Jika pelatihan hanya mengizinkan HTTP, putuskan mode demo dengan data/akun uji secara terpisah dahulu; jangan memublikasikan akun dan dokumen nyata lewat HTTP.

## Berkas deployment

- `backend/deployment.py`: wrapper factory utama, memeriksa konfigurasi produksi dan membatasi Host yang diterima.
- `deploy/ec2/gunicorn.conf.py`: satu worker, empat thread, localhost:3000, tanpa reloader/preload; satu background worker antrean.
- `deploy/ec2/nginx-amiga.conf`: listener publik port 80; isi server_name dengan hostname/IP tujuan, cek konflik konfigurasi Nginx existing sebelum dipasang.
- `deploy/ec2/amiga.service`: unit systemd non-root; source di `/opt/amiga`, dokumen di `/var/lib/amiga/documents`, runtime di `/run/amiga`.
- `deploy/ec2/.env.example`: konfigurasi server tanpa nilai rahasia.
- `deploy/ec2/preflight.py`: pemeriksaan offline yang hanya mencetak kode kesalahan, tanpa koneksi database/cloud atau nilai rahasia.
- `deploy/ec2/package_release.py`: paket source saja, tanpa akun, database, dokumen klien, kredensial atau backup.

Konfigurasi laptop tetap terpisah. `UPLOAD_DIR` sekarang dapat ditentukan lewat environment agar dokumen server tetap tersimpan di luar folder source saat update.

## Persiapan di EC2 setelah akses tersedia

1. Verifikasi instance milik kelompok, cloud-init selesai, OS/arsitektur, Python 3.12+, RAM/disk, port publik 80 dan port internal 3000 tidak dipakai aplikasi lain, instance role dan endpoint HTTPS.
2. Clone repo privat melalui metode akses yang disetujui pemilik/mentor. Token tidak boleh dimasukkan ke URL git, script, shell history, screenshot atau source. Jika memakai arsip source terfilter, verifikasi SHA256 lalu ekstrak di `/opt/amiga` yang baru/kosong; jangan menimpa deployment lain.
3. Buat user service `amiga`, folder konfigurasi `/etc/amiga` dan state `/var/lib/amiga`. Source dibaca service; kredensial hanya dapat dibaca root/group service.
4. Pada Amazon Linux, periksa paket PostgreSQL yang cocok dengan AMI. Jangan jalankan initdb bila cluster lama sudah ada. Buat database dan user aplikasi tersendiri; PostgreSQL hanya listen localhost. Jangan membuka port 5432 di security group.
5. Salin contoh konfigurasi ke `/etc/amiga/amiga.env`, isi database, SECRET_KEY acak, email pemilik dan endpoint HTTPS yang benar. Simpan API key Luna privat di `/etc/amiga/openai.key` (root:amiga, mode 0640); jangan commit nilainya. Telegram boleh kosong. Tanpa key Luna, tahap analisis awal tidak siap.
6. Instal dependency di virtualenv Linux:

```bash
cd /opt/amiga
python3.12 -m venv .venv
.venv/bin/python -m pip install -r deploy/ec2/requirements.txt
.venv/bin/python deploy/ec2/preflight.py --env-file /etc/amiga/amiga.env
```

7. Tinjau migrasi `001`–`004`. Untuk database AMIGA baru yang telah disiapkan, jalankan inisialisasi eksplisit sebagai user service, dengan direktori dokumen sudah dimiliki `amiga`:

```bash
sudo -u amiga /opt/amiga/.venv/bin/python -m backend.manage --env-file /etc/amiga/amiga.env init-db
```

8. Setelah preflight lulus dan database siap, pasang unit systemd lalu jalankan service:

```bash
sudo install -m 0644 deploy/ec2/amiga.service /etc/systemd/system/amiga.service
sudo systemctl daemon-reload
sudo systemctl enable --now amiga
sudo systemctl status amiga --no-pager
curl --fail http://127.0.0.1:3000/health
# Setelah server_name Nginx diisi dan konfigurasi existing diperiksa:
sudo nginx -t
# Terapkan/reload Nginx hanya setelah validasi dan tujuan instance terverifikasi.
```

Port yang dilaporkan kepada mentor adalah **80**, bukan port backend 3000. Pemeriksaan publik memakai `http://IP/health` atau endpoint HTTPS yang disediakan, tanpa `:3000`.

9. Pemilik membuat password sendiri. Gunakan `backend.manage setup-admin` secara interaktif pada server, atau capability aktivasi sekali pakai dari operator tepercaya. Jangan mengirim password ke Codex atau repo. Login pertama via HTTPS dengan email `/atmin`; berikutnya email biasa. Pendaftaran reviewer `/review` atau `/view` dan izin admin tetap berlaku.
10. Uji HTTPS dari luar: login/logout, cookie Secure/HttpOnly, isolasi tenant, unggah invoice fiktif, ekstraksi Nova, analisis Luna, konfirmasi uploader, klaim reviewer, voucher dan arsip. Telegram tidak diuji dengan mengirim ke klien nyata tanpa instruksi terpisah.

## Update dan pemulihan

Backup PostgreSQL dan direktori dokumen secara privat sebelum migrasi/update. Hentikan hanya `amiga.service`, terapkan source/migrasi yang ditinjau dan restart service itu. Jangan memakai `pkill node`, `pkill python`, atau menghapus database untuk menyelesaikan konflik port. Source versi sebelumnya dapat dikembalikan, tetapi rollback database harus mengikuti migrasi dan backup yang sesuai.

```bash
sudo journalctl -u amiga -n 80 --no-pager
sudo systemctl restart amiga
```

Jangan melaporkan URL live sampai server, HTTPS, login, database dan AI diuji. Form pelaporan pada PDF belum diisi otomatis.

Rujukan: [Flask/Gunicorn](https://flask.palletsprojects.com/en/stable/deploying/gunicorn/), [kredensial Boto3 melalui instance role](https://docs.aws.amazon.com/boto3/latest/guide/credentials.html), [kemampuan Nova Lite dan Micro](https://docs.aws.amazon.com/nova/latest/userguide/what-is-nova.html).
