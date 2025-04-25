from werkzeug.security import generate_password_hash
import psycopg2


def get_db_connection():
    conn = psycopg2.connect(
        host="localhost",
        port="5432",
        database="postgres",
        user="postgres",
        password="admin"
    )
    return conn


def create_admin():
    # Admin bilgileri
    admin_email = "admin@kostu.com"
    admin_password = "admin123"  # İstediğiniz şifreyi buraya yazın
    hashed_password = generate_password_hash(admin_password)

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Önce varolan admin kaydını kontrol et
        cur.execute("SELECT admin_id FROM emre_odev.admin WHERE email = %s", (admin_email,))
        existing_admin = cur.fetchone()

        if existing_admin:
            # Admin varsa güncelle
            cur.execute("""
                UPDATE emre_odev.admin 
                SET password = %s 
                WHERE email = %s
            """, (hashed_password, admin_email))
            print("Admin şifresi güncellendi")
        else:
            # Admin yoksa yeni kayıt oluştur
            cur.execute("""
                INSERT INTO emre_odev.admin (ad, soyad, email, password)
                VALUES (%s, %s, %s, %s)
            """, ('Admin', 'User', admin_email, hashed_password))
            print("Yeni admin oluşturuldu")

        conn.commit()
        print(f"Admin e-posta: {admin_email}")
        print(f"Admin şifre: {admin_password}")  # Güvenlik için gerçek uygulamada bunu yazdırmayın

    except Exception as e:
        print(f"Hata oluştu: {str(e)}")
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


if __name__ == "__main__":
    create_admin()