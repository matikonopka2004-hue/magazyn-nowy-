import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, Text
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from datetime import datetime
import time

# --- 1. KONFIGURACJA STRONY ---
st.set_page_config(page_title="Magazyn Pro", layout="wide")

# --- 2. BAZA DANYCH ---
Base = declarative_base()

class Kategoria(Base):
    __tablename__ = 'kategorie'
    id = Column(Integer, primary_key=True)
    nazwa = Column(String, nullable=False)
    opis = Column(Text)
    # Relacje
    produkty = relationship("Produkt", back_populates="kategoria_rel", cascade="all, delete-orphan")

class Produkt(Base):
    __tablename__ = 'produkty'
    id = Column(Integer, primary_key=True)
    nazwa = Column(String, nullable=False)
    liczba = Column(Integer, default=0)
    cena = Column(Float, default=0.0)
    zdjecie_url = Column(String, nullable=True) 
    kategoria_id = Column(Integer, ForeignKey('kategorie.id'), nullable=False)
    kategoria_rel = relationship("Kategoria", back_populates="produkty")

# Baza danych
DATABASE_URL = "sqlite:///magazyn_fixed.db" # Zmieniłem nazwę, żeby wymusić czysty start
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

def get_session():
    return Session()

# --- 3. FUNKCJE LOGICZNE ---

def dodaj_kategorie(nazwa, opis):
    with get_session() as session:
        nowa = Kategoria(nazwa=nazwa, opis=opis)
        session.add(nowa)
        session.commit()

def usun_kategorie(id_kat):
    with get_session() as session:
        kat = session.query(Kategoria).filter_by(id=id_kat).first()
        if kat:
            if kat.produkty:
                return False, "⛔ Kategoria nie jest pusta!"
            session.delete(kat)
            session.commit()
            return True, "✅ Usunięto."
        return False, "Brak kategorii."

def dodaj_produkt(nazwa, liczba, cena, kategoria_id, img_url):
    with get_session() as session:
        nowy = Produkt(
            nazwa=nazwa, 
            liczba=liczba, 
            cena=cena, 
            kategoria_id=kategoria_id, 
            zdjecie_url=img_url
        )
        session.add(nowy)
        session.commit()

def sprzedaj_produkt(id_prod):
    with get_session() as session:
        prod = session.query(Produkt).filter_by(id=id_prod).first()
        if prod and prod.liczba > 0:
            prod.liczba -= 1
            info = {
                "produkt": prod.nazwa,
                "cena": prod.cena,
                "data": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            session.commit()
            return True, "Sprzedano", info
        elif prod and prod.liczba == 0:
            return False, "⛔ Brak towaru!", None
        else:
            return False, "Błąd produktu", None

def usun_produkt_calowicie(id_prod):
    with get_session() as session:
        prod = session.query(Produkt).filter_by(id=id_prod).first()
        if prod:
            wartosc = prod.liczba * prod.cena
            nazwa = prod.nazwa
            ilosc = prod.liczba
            session.delete(prod)
            session.commit()
            return f"Usunięto: {nazwa} (Strata: {wartosc:.2f} PLN)"
    return None

# --- 4. BEZPIECZNE POBIERANIE DANYCH (SAFE LOADING) ---
# To jest kluczowa poprawka. Pobieramy dane i od razu zamykamy sesję,
# przekazując do UI czyste słowniki (dictionaries), a nie obiekty bazy.

safe_products = []
safe_categories = {} # Słownik id -> nazwa

with get_session() as session:
    # Pobierz wszystko
    kats = session.query(Kategoria).all()
    prods = session.query(Produkt).all()
    
    # Mapuj kategorie do słownika
    for k in kats:
        safe_categories[k.id] = k.nazwa
        
    # Mapuj produkty do listy słowników
    for p in prods:
        safe_products.append({
            "id": p.id,
            "nazwa": p.nazwa,
            "liczba": p.liczba,
            "cena": p.cena,
            "wartosc": p.liczba * p.cena,
            "kategoria_id": p.kategoria_id,
            "kategoria_nazwa": safe_categories.get(p.kategoria_id, "Nieznana"),
            "zdjecie_url": p.zdjecie_url
        })

# --- 5. UI (DASHBOARD) ---

st.title("📊 Centrum Magazynowe")

# Sprawdzamy czy są jakiekolwiek produkty w bezpiecznej liście
if safe_products:
    # Tworzymy DataFrame z bezpiecznych danych
    df = pd.DataFrame(safe_products)

    # METRYKI
    m1, m2, m3 = st.columns(3)
    m1.metric("Wartość magazynu", f"{df['wartosc'].sum():.2f} PLN")
    m2.metric("Liczba produktów (SKU)", len(df))
    m3.metric("Łącznie sztuk", df['liczba'].sum())

    st.divider()

    # WYKRESY
    c_chart1, c_chart2 = st.columns(2)
    with c_chart1:
        st.subheader("Stany (Ilość)")
        st.bar_chart(df.set_index("nazwa")["liczba"], color="#4CAF50")
    
    with c_chart2:
        st.subheader("Wartość w kategoriach")
        # Grupujemy po nazwie kategorii
        if "kategoria_nazwa" in df.columns:
            st.bar_chart(df.groupby("kategoria_nazwa")["wartosc"].sum(), color="#FF9800")
else:
    st.info("👋 Witaj! Magazyn jest pusty. Dodaj pierwsze produkty w zakładce 'Dodawanie'.")

st.divider()

# --- 6. ZAKŁADKI ---
tab1, tab2 = st.tabs(["🛒 Lista i Sprzedaż", "➕ Dodawanie i Edycja"])

# ZAKŁADKA 1: SPRZEDAŻ
with tab1:
    st.header("Terminal Sprzedażowy")
    
    col_filt, _ = st.columns([2,3])
    alarm_mode = col_filt.checkbox("Tylko stany alarmowe (< 5 szt.)")

    if safe_products:
        for p in safe_products:
            # Filtrowanie
            if alarm_mode and p['liczba'] >= 5:
                continue

            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([1, 3, 1, 1])
                
                # Zdjęcie
                if p['zdjecie_url']:
                    c1.image(p['zdjecie_url'], width=80)
                else:
                    c1.markdown("📦")
                
                # Dane
                c2.subheader(p['nazwa'])
                kolor = "red" if p['liczba'] < 5 else "green"
                c2.markdown(f"Kategoria: **{p['kategoria_nazwa']}**")
                c2.markdown(f"Stan: :{kolor}[**{p['liczba']}**] | Cena: **{p['cena']:.2f} PLN**")
                
                # Akcje - Używamy ID ze słownika
                if c3.button("💰 Sprzedaj", key=f"sell_{p['id']}", use_container_width=True):
                    ok, msg, kwit = sprzedaj_produkt(p['id'])
                    if ok:
                        st.toast(msg, icon="✅")
                        st.success(f"🧾 PARAGON: {kwit['produkt']} - {kwit['cena']} PLN ({kwit['data']})")
                        time.sleep(1.5)
                        st.rerun()
                    else:
                        st.error(msg)
                
                if c4.button("❌ Usuń", key=f"del_{p['id']}", type="primary", use_container_width=True):
                    raport = usun_produkt_calowicie(p['id'])
                    if raport:
                        st.warning(raport)
                        time.sleep(2)
                        st.rerun()
    else:
        st.write("Brak produktów.")

# ZAKŁADKA 2: DODAWANIE
with tab2:
    c_left, c_right = st.columns(2)
    
    with c_left:
        st.subheader("1. Kategorie")
        with st.form("kat_form"):
            n_kat = st.text_input("Nazwa kategorii")
            d_kat = st.text_input("Opis")
            if st.form_submit_button("Dodaj Kategorię"):
                if n_kat:
                    dodaj_kategorie(n_kat, d_kat)
                    st.success("Dodano!")
                    st.rerun()
                else:
                    st.error("Podaj nazwę.")
        
        st.write("Twoje kategorie:")
        for kid, kname in safe_categories.items():
            col_k1, col_k2 = st.columns([3,1])
            col_k1.write(f"🔹 {kname}")
            if col_k2.button("Usuń", key=f"rm_k_{kid}"):
                ok, m = usun_kategorie(kid)
                if ok: st.rerun()
                else: st.error(m)

    with c_right:
        st.subheader("2. Produkty")
        if not safe_categories:
            st.warning("Najpierw dodaj kategorię!")
        else:
            with st.form("prod_form"):
                n_prod = st.text_input("Nazwa")
                n_ilosc = st.number_input("Ilość", min_value=0, step=1)
                n_cena = st.number_input("Cena", min_value=0.01, step=0.01)
                
                # Odwrócenie słownika nazwa -> id
                mapa_nazw = {v: k for k, v in safe_categories.items()}
                wybor_kat = st.selectbox("Kategoria", list(mapa_nazw.keys()))
                
                n_url = st.text_input("Zdjęcie URL (opcjonalnie)")
                
                if st.form_submit_button("Dodaj Produkt"):
                    if n_prod:
                        dodaj_produkt(n_prod, n_ilosc, n_cena, mapa_nazw[wybor_kat], n_url)
                        st.success("Dodano produkt!")
                        st.rerun()
                    else:
                        st.error("Podaj nazwę!")
