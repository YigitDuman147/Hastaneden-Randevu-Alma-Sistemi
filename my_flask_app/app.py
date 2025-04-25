from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import psycopg2.extras
import json
from datetime import datetime, timedelta
# Database connection manager
#from werkzeug.security import check_password_hash
class DatabaseManager:
    def __init__(self, host, port, database, user, password):
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password

    def connect(self):
        return psycopg2.connect(
            host=self.host,
            port=self.port,
            database=self.database,
            user=self.user,
            password=self.password
        )

class AdminManager:
    def __init__(self, db_manager):
        self.db_manager = db_manager
    def get_admin_by_email(self, email):
        with self.db_manager.connect() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute("""
                    SELECT admin_id, password 
                    FROM emre_odev.admin 
                    WHERE email = %s
                """, (email,))
                return cur.fetchone()
    def get_all_doctors(self):
        with self.db_manager.connect() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute("""
                    SELECT d.doktor_id as id, d.ad, d.soyad, d.email, b.ad as bolum 
                    FROM emre_odev.doktor d
                    LEFT JOIN emre_odev.bolum b ON d.bolum_id = b.bolum_id
                    ORDER BY d.ad, d.soyad
                """)
                return cur.fetchall()

    def add_doctor(self, ad, soyad, email, password, bolum_id):
        try:
            with self.db_manager.connect() as conn:
                with conn.cursor() as cur:
                    # Önce bölümün var olduğunu kontrol edelim
                    cur.execute("SELECT bolum_id FROM emre_odev.bolum WHERE bolum_id = %s", (bolum_id,))
                    if not cur.fetchone():
                        raise Exception("Seçilen bölüm bulunamadı")

                    # En yüksek doktor_id'yi bulalım
                    cur.execute("SELECT COALESCE(MAX(doktor_id), 0) + 1 FROM emre_odev.doktor")
                    next_id = cur.fetchone()[0]

                    # Doktoru ekleyelim
                    cur.execute("""
                        INSERT INTO emre_odev.doktor 
                        (doktor_id, ad, soyad, email, password, bolum_id)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        RETURNING doktor_id
                    """, (next_id, ad, soyad, email, password, bolum_id))
                    conn.commit()

                    print(f"Doktor eklendi. ID: {next_id}, Bölüm ID: {bolum_id}")  # Log ekleyelim
                    return cur.fetchone()[0]
        except psycopg2.Error as e:
            print("Veritabanı hatası:", e.pgerror)
            raise Exception(f"Veritabanı hatası: {str(e)}")

    def delete_doctor(self, doctor_id):
        with self.db_manager.connect() as conn:
            with conn.cursor() as cur:
                # Önce doktorun randevularını sil
                cur.execute("DELETE FROM emre_odev.randevu WHERE doktor_id = %s", (doctor_id,))
                # Sonra doktoru sil
                cur.execute("DELETE FROM emre_odev.doktor WHERE doktor_id = %s", (doctor_id,))
                conn.commit()

    def get_all_departments(self):
        with self.db_manager.connect() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute("SELECT bolum_id as id, ad FROM emre_odev.bolum ORDER BY ad")
                return cur.fetchall()

    def get_doctor_by_id(self, doctor_id):
        with self.db_manager.connect() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute("""
                    SELECT d.*, b.ad as bolum_adi 
                    FROM emre_odev.doktor d
                    LEFT JOIN emre_odev.bolum b ON d.bolum_id = b.bolum_id
                    WHERE d.doktor_id = %s
                """, (doctor_id,))
                return cur.fetchone()

    def update_doctor(self, doctor_id, ad, soyad, email, bolum_id):
        with self.db_manager.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE emre_odev.doktor 
                    SET ad = %s, soyad = %s, email = %s, bolum_id = %s
                    WHERE doktor_id = %s
                    RETURNING doktor_id
                """, (ad, soyad, email, bolum_id, doctor_id))
                conn.commit()
                return cur.fetchone()[0]


# User manager for handling user-related operations
class UserManager:
    def __init__(self, db_manager):
        self.db_manager = db_manager

    def get_user_by_email(self, email):
        with self.db_manager.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT hasta_id, password FROM emre_odev.hasta WHERE email = %s", (email,))
                return cur.fetchone()

    def create_user(self, first_name, last_name, email, password):
        hashed_password = generate_password_hash(password)
        with self.db_manager.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO emre_odev.hasta (ad, soyad, email, password) VALUES (%s, %s, %s, %s)",
                    (first_name, last_name, email, hashed_password)
                )
                conn.commit()

    def get_user_appointments(self, user_id):
        with self.db_manager.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT r.randevu_id, d.ad AS doktor_ad, d.soyad AS doktor_soyad, b.ad AS bolum_ad, r.randevu_tarih, r.randevu_saat
                    FROM emre_odev.randevu r
                    JOIN emre_odev.doktor d ON r.doktor_id = d.doktor_id
                    JOIN emre_odev.bolum b ON d.bolum_id = b.bolum_id
                    WHERE r.hasta_id = %s
                    ORDER BY r.randevu_tarih, r.randevu_saat
                    """,
                    (user_id,)
                )
                return cur.fetchall()
class DoctorManager:
    def __init__(self, db_manager):
        self.db_manager = db_manager

    def get_doktor_by_email(self, email):
        with self.db_manager.connect() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute("SELECT doktor_id, password FROM emre_odev.doktor WHERE email = %s", (email,))
                return cur.fetchone()

    def get_doktor_appointments(self, doktor_id):
        with self.db_manager.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT h.ad AS hasta_ad, r.randevu_tarih, r.randevu_saat
                    FROM emre_odev.randevu r
                    JOIN emre_odev.hasta h ON r.hasta_id = h.hasta_id
                    WHERE r.doktor_id = %s
                    ORDER BY r.randevu_tarih, r.randevu_saat
                """, (doktor_id,))
                return cur.fetchall()

    # DoctorManager sınıfında
    def get_uzmanlik_alanlari(self):
        with self.db_manager.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT bolum_id, ad FROM emre_odev.bolum ORDER BY ad")
                return cur.fetchall()

    def update_doktor_profile(self, doktor_id, bolum_id, calisma_saatleri):
        with self.db_manager.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE emre_odev.doktor
                    SET bolum_id = %s, calisma_saatleri = %s
                    WHERE doktor_id = %s
                """, (bolum_id, calisma_saatleri, doktor_id))
                conn.commit()

    def get_doktor_profile(self, doktor_id):
        with self.db_manager.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT ad, soyad, uzmanlik, calisma_saatleri
                    FROM emre_odev.doktor
                    WHERE doktor_id = %s
                """, (doktor_id,))
                return cur.fetchone()

    def get_doktor_appointments_by_status(self, doktor_id):
        with self.db_manager.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT h.ad AS hasta_ad, r.randevu_tarih, r.randevu_saat
                    FROM emre_odev.randevu r
                    JOIN emre_odev.hasta h ON r.hasta_id = h.hasta_id
                    WHERE r.doktor_id = %s
                    ORDER BY r.randevu_tarih, r.randevu_saat
                """, (doktor_id,))
                all_appointments = cur.fetchall()

                today = datetime.now().date()
                past = [apt for apt in all_appointments if apt[1] < today]
                upcoming = [apt for apt in all_appointments if apt[1] >= today]

                return past, upcoming

    def get_doktor_by_id(self, doktor_id):  # self parametresi eklendi
        with self.db_manager.connect() as conn:  # self.db_manager kullanımı
            with conn.cursor() as cur:
                cur.execute("SELECT ad, soyad, uzmanlik, calisma_saatleri FROM emre_odev.doktor WHERE doktor_id = %s",
                            (doktor_id,))
                return cur.fetchone()


# Appointment manager for handling appointment-related operations
class AppointmentManager:
    def __init__(self, db_manager):
        self.db_manager = db_manager

    def get_departments(self):
        with self.db_manager.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT bolum_id, ad FROM emre_odev.bolum ORDER BY ad")
                return cur.fetchall()

    def get_doctors_by_department(self, bolum_id):
        with self.db_manager.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT doktor_id, ad, soyad FROM emre_odev.doktor WHERE bolum_id = %s", (bolum_id,))
                return cur.fetchall()


    def get_working_hours(self, doktor_id, tarih):
        with self.db_manager.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT calisma_saatleri FROM emre_odev.doktor WHERE doktor_id = %s", (doktor_id,))
                doktor_calisma_saatleri = cur.fetchone()

                if not doktor_calisma_saatleri or not doktor_calisma_saatleri[0]:
                    return []

                # Çalışma saatlerini JSON formatından parse et
                try:
                    calisma_saatleri = json.loads(doktor_calisma_saatleri[0])  # Örn: {"Pazartesi": "09:00-17:00"}
                except json.JSONDecodeError:
                    return []

                # Tarihi gün adına çevir (örn: "2025-01-18" -> "Cumartesi")
                gun_adi = datetime.strptime(tarih, "%Y-%m-%d").strftime("%A")

                # Çalışma saatlerini al
                if gun_adi not in calisma_saatleri:
                    return []

                baslangic, bitis = calisma_saatleri[gun_adi].split("-")  # Örn: "09:00-17:00"
                current = datetime.strptime(baslangic, "%H:%M")
                end = datetime.strptime(bitis, "%H:%M")
                saat_araliklari = []
                while current < end:
                    saat_araliklari.append(current.strftime("%H:%M"))
                    current += timedelta(minutes=30)

                return saat_araliklari

    def get_available_hours(self, doktor_id, tarih):
        working_hours = self.get_working_hours(doktor_id, tarih)  # Yeni fonksiyonu çağır
        if not working_hours:
            return []

        with self.db_manager.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT randevu_saat 
                    FROM emre_odev.randevu 
                    WHERE doktor_id = %s AND randevu_tarih = %s
                    """,
                    (doktor_id, tarih)
                )
                booked_hours = {row[0] for row in cur.fetchall()}
                available_hours = [saat for saat in working_hours if saat not in booked_hours]
                return available_hours

    def book_appointment(self, user_id, doktor_id, tarih, saat, bolum_id):
        with self.db_manager.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO emre_odev.randevu (hasta_id, doktor_id, bolum_id, randevu_tarih, randevu_saat) 
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (user_id, doktor_id, bolum_id, tarih, saat)
                )
                conn.commit()


# Flask app configuration
app = Flask(__name__)
app.secret_key = 'gergergert35345'

db_manager = DatabaseManager(
    host="localhost",
    port="5432",
    database="postgres",
    user="postgres",
    password="admin"
)

user_manager = UserManager(db_manager)
appointment_manager = AppointmentManager(db_manager)
doktor_manager = DoctorManager(db_manager)
admin_manager = AdminManager(db_manager)
@app.route('/')
def index():
    return render_template('index.html')



@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        admin = admin_manager.get_admin_by_email(email)
        if admin and check_password_hash(admin['password'], password):
            session['admin_id'] = admin['admin_id']
            flash("Admin olarak başarıyla giriş yaptınız.", "success")
            return redirect(url_for('admin_dashboard'))
        else:
            flash("Geçersiz e-posta veya şifre.", "danger")
    return render_template('admin_login.html')

@app.route('/admin_dashboard')
def admin_dashboard():
    if 'admin_id' not in session:
        flash("Bu sayfaya erişmek için admin girişi yapmalısınız.", "warning")
        return redirect(url_for('admin_login'))
    return render_template('admin_dashboard.html')

# Flask route'ları
@app.route('/admin/doctors', methods=['GET'])
def get_doctors():
    if 'admin_id' not in session:
        return jsonify({'error': 'Yetkisiz erişim'}), 401
    try:
        doctors = admin_manager.get_all_doctors()
        return jsonify([dict(doc) for doc in doctors])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin/doctors/add', methods=['POST'])
def add_doctor():
    if 'admin_id' not in session:
        return jsonify({'error': 'Yetkisiz erişim'}), 401
    try:
        data = request.get_json()
        hashed_password = generate_password_hash(data['password'])
        doctor_id = admin_manager.add_doctor(
            data['ad'],
            data['soyad'],
            data['email'],
            hashed_password,
            data['bolum_id']
        )
        return jsonify({'success': True, 'message': 'Doktor başarıyla eklendi'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/admin/doctors/add', methods=['POST'])
def admin_add_doctor():
    if 'admin_id' not in session:
        return jsonify({'error': 'Yetkisiz erişim'}), 401
    try:
        data = request.get_json()
        print("Gelen veri:", data)  # Gelen veriyi kontrol edelim

        # Veriyi kontrol et
        if not data.get('bolum_id'):
            return jsonify({'error': 'Bölüm seçilmedi'}), 400

        # String olarak gelen bolum_id'yi integer'a çevirelim
        bolum_id = int(data['bolum_id'])

        hashed_password = generate_password_hash(data['password'])

        doctor_id = admin_manager.add_doctor(
            data['ad'],
            data['soyad'],
            data['email'],
            hashed_password,
            bolum_id  # Integer olarak gönderiyoruz
        )
        return jsonify({'success': True, 'message': 'Doktor başarıyla eklendi'})
    except Exception as e:
        print("Hata:", str(e))
        return jsonify({'error': str(e)}), 500
@app.route('/admin/doctors/<int:doctor_id>', methods=['DELETE'])
def delete_doctor(doctor_id):
    if 'admin_id' not in session:
        return jsonify({'error': 'Yetkisiz erişim'}), 401
    try:
        admin_manager.delete_doctor(doctor_id)
        return jsonify({'success': True, 'message': 'Doktor başarıyla silindi'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin/departments', methods=['GET'])
def get_departments():
    if 'admin_id' not in session:
        return jsonify({'error': 'Yetkisiz erişim'}), 401
    try:
        departments = admin_manager.get_all_departments()
        return jsonify([dict(dept) for dept in departments])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin_panel')
def admin_panel():
    if 'admin_id' not in session:
        flash("Bu sayfaya erişmek için admin girişi yapmalısınız.", "warning")
        return redirect(url_for('admin_login'))
    return render_template('admin_dashboard.html')
@app.route('/login', methods=['GET', 'POST'])
def login_user():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        user = user_manager.get_user_by_email(email)

        if user and check_password_hash(user[1], password):
            session['user_id'] = user[0]
            flash("Başarıyla giriş yaptınız.", "success")
            return redirect(url_for('dashboard'))
        else:
            flash("Geçersiz e-posta veya şifre.", "danger")
    return render_template('login.html')


@app.route('/doctor_login', methods=['GET', 'POST'])
def doctor_login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        doktor = doktor_manager.get_doktor_by_email(email)
        # Burada şifre karşılaştırması yapıyoruz
        if doktor and doktor['password'] == password:  # Eğer hash kullanmıyorsanız
        # VEYA hash kullanıyorsanız:
        # if doktor and check_password_hash(doktor['password'], password):
            session['doktor_id'] = doktor['doktor_id']
            flash("Doktor olarak başarıyla giriş yaptınız.", "success")
            return redirect(url_for('doctor_menu'))
        else:
            flash("Geçersiz e-posta veya şifre.", "danger")
    return render_template('doctor_login.html')


@app.route('/doctor_menu')
def doctor_menu():
    if 'doktor_id' not in session:
        flash("Bu sayfaya erişmek için giriş yapmalısınız.", "warning")
        return redirect(url_for('doctor_login'))

    doktor_id = session['doktor_id']
    doktor = doktor_manager.get_doktor_by_id(doktor_id)

    if doktor is None:
        flash("Doktor bilgisi bulunamadı.", "error")
        return redirect(url_for('doctor_login'))

    # Randevuları getir
    past_appointments, upcoming_appointments = doktor_manager.get_doktor_appointments_by_status(doktor_id)

    return render_template('doctor_menu.html',
                           doktor=doktor,
                           past_appointments=past_appointments,
                           upcoming_appointments=upcoming_appointments)


@app.route('/doctor/profile', methods=['GET', 'POST'])
def doctor_profile():
    if 'doktor_id' not in session:
        flash("Bu sayfaya erişmek için giriş yapmalısınız.", "warning")
        return redirect(url_for('doctor_login'))

    doktor_id = session['doktor_id']
    doktor = doktor_manager.get_doktor_by_id(doktor_id)
    bolumler = doktor_manager.get_uzmanlik_alanlari()

    if request.method == 'POST':
        bolum_id = request.form['bolum_id']
        calisma_baslangic = request.form['calisma_baslangic']
        calisma_bitis = request.form['calisma_bitis']
        calisma_saatleri = f"{calisma_baslangic} - {calisma_bitis}"

        try:
            doktor_manager.update_doktor_profile(doktor_id, bolum_id, calisma_saatleri)
            flash("Profil başarıyla güncellendi.", "success")
            return redirect(url_for('doctor_profile'))
        except Exception as e:
            flash("Profil güncellenirken bir hata oluştu.", "danger")

    return render_template('doctor_profile.html', doktor=doktor, bolumler=bolumler)
@app.route('/doctor/logout')
def doctor_logout():
    if 'doktor_id' in session:
        session.clear()
        flash("Başarıyla çıkış yaptınız.", "success")
    return redirect(url_for('doctor_login'))


@app.route('/doctor/appointments')
def doctor_appointments():
    if 'doktor_id' not in session:
        flash("Bu sayfaya erişmek için giriş yapmalısınız.", "warning")
        return redirect(url_for('doctor_login'))

    doktor_id = session['doktor_id']
    past_appointments, upcoming_appointments = doktor_manager.get_doktor_appointments_by_status(doktor_id)
    doktor = doktor_manager.get_doktor_by_id(doktor_id)

    return render_template('doctor_appointments.html',
                           doktor=doktor,
                           past_appointments=past_appointments,
                           upcoming_appointments=upcoming_appointments)

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']
        # Şifre sıfırlama e-posta süreci veya manuel sıfırlama
        flash("Şifre sıfırlama bağlantısı e-posta adresinize gönderildi.", "info")
        return redirect(url_for('login_user'))
    return render_template('forgot_password.html')


@app.route('/submit', methods=['POST'])
def submit():
    first_name = request.form['first_name']
    last_name = request.form['last_name']
    email = request.form['email']
    password = request.form['password']

    # Parola doğrulama
    if password != request.form['confirm_password']:
        flash("Şifreler uyuşmuyor.", "danger")
        return redirect(url_for('index'))

    try:
        user_manager.create_user(first_name, last_name, email, password)
        flash("Kaydınız gerçekleşmiştir. Sisteme giriş yaparak randevu alabilirsiniz.", "success")
        return redirect(url_for('index'))
    except Exception as e:
        return f"An error occurred: {str(e)}"

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        flash("Lütfen önce giriş yapın.", "danger")
        return redirect(url_for('login'))

    user_id = session['user_id']
    user_appointments = user_manager.get_user_appointments(user_id)
    return render_template('dashboard.html', randevular=user_appointments)

@app.route('/appointment')
def appointment():
    try:
        bolumler = appointment_manager.get_departments()
        return render_template('appointment.html', bolumler=bolumler)
    except Exception as e:
        return f"Bir hata oluştu: {str(e)}"

@app.route('/delete_appointment', methods=['POST'])
def delete_appointment():
    if 'user_id' not in session:
        flash("Lütfen önce giriş yapın.", "danger")
        return redirect(url_for('login'))

    randevu_id = request.form['randevu_id']
    try:
        with db_manager.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM emre_odev.randevu WHERE randevu_id = %s", (randevu_id,))
                conn.commit()
        flash("Randevunuz başarıyla iptal edildi.", "success")
    except Exception as e:
        flash(f"Bir hata oluştu: {str(e)}", "danger")

    return redirect(url_for('dashboard'))



@app.route('/book_appointment', methods=['POST'])
def book_appointment():
    if 'user_id' not in session:
        flash("Lütfen giriş yapın.", "danger")
        return redirect(url_for('login'))

    doktor_id = request.form['doktor_id']
    tarih = request.form['tarih']
    saat = request.form['saat']
    bolum_id = request.form['bolum_id']

    try:
        appointment_manager.book_appointment(session['user_id'], doktor_id, tarih, saat, bolum_id)
        flash("Randevunuz başarıyla alındı.", "success")
        return redirect(url_for('dashboard'))
    except Exception as e:
        return f"Bir hata oluştu: {str(e)}"

@app.route('/get_available_hours')
def get_available_hours():
    doktor_id = request.args.get('doktor_id')
    tarih = request.args.get('tarih')
    try:
        hours = appointment_manager.get_available_hours(doktor_id, tarih)
        return jsonify(hours)
    except Exception as e:
        return jsonify({"error": str(e)})


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash("Başarıyla çıkış yaptınız.", "success")
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
