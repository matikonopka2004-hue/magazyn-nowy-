import streamlit as st
from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, Text
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from sqlalchemy.exc import IntegrityError

# --- KONFIGURACJA BAZY DANYCH (Model) ---
Base = declarative_base()

class Kategoria(Base):
    __tablename__ = 'kategorie'
    id = Column(Integer, primary_key=True)
    nazwa = Column(String, nullable=False)
    opis = Column(Text)
    # Relacja: jedna kategoria ma wiele produktów
    produkty = relationship("Produkt", back_populates="kategoria_rel")

class Produkt(Base):
    __tablename__ = 'produkty'
    id = Column(Integer, primary_key=True)
    nazwa = Column(String, nullable=False)
    liczba = Column(Integer, default=0)
    cena = Column(Float, default=0.0)
    # Klucz obcy wskazujący na kategorie
    kategoria_id = Column(Integer, ForeignKey('kategorie.id'), nullable=False)
    
    # Relacja zwrotna
    kategoria_rel = relationship("Kategoria", back_populates="produkty")

# Połączenie z bazą (SQLite tworzy plik lokalnie)
# UWAGA: Na Streamlit Cloud ten plik zniknie po restarcie apki!
DATABASE_URL = "sqlite:///magazyn.db" 
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

# --- FUNKCJE POMOCNICZE (Logika) ---
def get_session():
    return Session()

def dodaj_kategorie(nazwa, opis):
    session = get_session()
    nowa = Kategoria(nazwa=nazwa, opis=opis)
    session.add(nowa)
    session.commit()
    session.close()

def usun_kategorie(id_kat):
    session = get_session()
    try:
        kat = session.query(Kategoria).filter_by(id=id_kat).first()
        if kat:
            # Sprawdź czy są produkty (zabezpieczenie logiczne)
            if kat.produkty:
                return False, "Nie można usunąć kategorii, która zawiera produkty! Najpierw usuń produkty."
            session.delete(kat)
            session.commit()
            return True, "Usunięto kategorię."
        return False, "Nie znaleziono kategorii."
    except Exception as e:
        return False, str(e)
    finally:
        session.close()

def dodaj_produkt(nazwa, liczba, cena, kategoria_id):
    session = get_session()
    nowy = Produkt(nazwa=nazwa, liczba=liczba, cena=cena, kategoria_id=kategoria_id)
    session.add(nowy)
    session.commit()
    session.close()

def usun_produkt(id_prod):
    session = get_session()
    prod = session.query(Produkt).filter_by(id=id_prod).first()
    if prod:
        session.delete(prod)
        session.commit()
    session.close()

# --- INTERFEJS UŻYTKOWNIKA (Streamlit) ---
st.set_page_config(page_title="Menadżer Magazynu", layout="wide")
st.title("📦 System Zarządzania Produktami")

# Pobranie danych do wyświetlania
session = get_session()
kategorie_db = session.query(Kategoria).all()
produkty_db = session.query(Produkt).all()
session.close()

tab1, tab2 = st.tabs(["📂 Kategorie", "🛒 Produkty"])

# --- TAB 1: KATEGORIE ---
with tab1:
    st.header("Zarządzanie Kategoriami")
    
    # Formularz dodawania
    with st.form("form_kat"):
        col1, col2 = st.columns(2)
        new_kat_nazwa = col1.text_input("Nazwa kategorii")
        new_kat_opis = col2.text_input("Opis")
        submitted = st.form_submit_button("Dodaj Kategorię")
        if submitted and new_kat_nazwa:
            dodaj_kategorie(new_kat_nazwa, new_kat_opis)
            st.success(f"Dodano: {new_kat_nazwa}")
            st.rerun()

    st.divider()
    
    # Lista i usuwanie
    if kategorie_db:
        for kat in kategorie_db:
            c1, c2, c3 = st.columns([1, 3, 1])
            c1.write(f"**{kat.nazwa}**")
            c2.write(f"_{kat.opis}_")
            if c3.button("Usuń", key=f"del_kat_{kat.id}"):
                success, msg = usun_kategorie(kat.id)
                if success:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
    else:
        st.info("Brak kategorii. Dodaj pierwszą!")

# --- TAB 2: PRODUKTY ---
with tab2:
    st.header("Zarządzanie Produktami")

    if not kategorie_db:
        st.warning("Najpierw musisz dodać przynajmniej jedną kategorię, aby dodawać produkty.")
    else:
        # Formularz dodawania produktu
        with st.form("form_prod"):
            c1, c2, c3, c4 = st.columns(4)
            p_nazwa = c1.text_input("Nazwa produktu")
            p_liczba = c2.number_input("Ilość", min_value=0, step=1)
            p_cena = c3.number_input("Cena", min_value=0.0, step=0.01)
            
            # Mapowanie nazw kategorii na ID
            kat_opcje = {k.nazwa: k.id for k in kategorie_db}
            wybrana_kat_nazwa = c4.selectbox("Kategoria", list(kat_opcje.keys()))
            
            p_submit = st.form_submit_button("Dodaj Produkt")
            
            if p_submit and p_nazwa:
                dodaj_produkt(p_nazwa, p_liczba, p_cena, kat_opcje[wybrana_kat_nazwa])
                st.success("Dodano produkt!")
                st.rerun()

    st.divider()

    # Tabela produktów
    if produkty_db:
        # Przygotowanie danych pod st.dataframe dla ładniejszego wyglądu
        data = []
        for p in produkty_db:
            kat_nazwa = next((k.nazwa for k in kategorie_db if k.id == p.kategoria_id), "Nieznana")
            data.append({
                "ID": p.id,
                "Nazwa": p.nazwa,
                "Ilość": p.liczba,
                "Cena": f"{p.cena:.2f} PLN",
                "Kategoria": kat_nazwa
            })
        st.dataframe(data, use_container_width=True)

        # Sekcja usuwania po ID (prostsze niż przyciski przy każdym wierszu przy dużej ilości danych)
        st.subheader("Usuwanie produktu")
        col_del, _ = st.columns([1, 3])
        id_to_del = col_del.number_input("Podaj ID produktu do usunięcia", min_value=1, step=1)
        if col_del.button("Usuń produkt"):
            usun_produkt(id_to_del)
            st.rerun()
    else:
        st.info("Brak produktów w bazie.")

#2222222
import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, Text
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from datetime import datetime

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="Magazyn Pro", layout="wide")

# --- MODEL BAZY DANYCH (Bez zmian względem v2) ---
Base = declarative_base()

class Kategoria(Base):
    __tablename__ = 'kategorie'
    id = Column(Integer, primary_key=True)
    nazwa = Column(String, nullable=False)
    opis = Column(Text)
    produkty = relationship("Produkt", back_populates="kategoria_rel")

class Produkt(Base):
    __tablename__ = 'produkty'
    id = Column(Integer, primary_key=True)
    nazwa = Column(String, nullable=False)
    liczba = Column(Integer, default=0)
    cena = Column(Float, default=0.0)
    zdjecie_url = Column(String, nullable=True) 
    kategoria_id = Column(Integer, ForeignKey('kategorie.id'), nullable=False)
    kategoria_rel = relationship("Kategoria", back_populates="produkty")

# Setup Bazy
DATABASE_URL = "sqlite:///magazyn_v3.db" # Nowa wersja bazy
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

def get_session():
    return Session()

# --- FUNKCJE LOGIKI ---
def sprzedaj_produkt(id_prod):
    session = get_session()
    prod = session.query(Produkt).filter_by(id=id_prod).first()
    paragon_info = None
    
    if prod and prod.liczba > 0:
        prod.liczba -= 1
        # Generowanie treści paragonu
        paragon_info = {
            "produkt": prod.nazwa,
            "cena": prod.cena,
            "data": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        session.commit()
        msg = "Sprzedano produkt."
        success = True
    elif prod and prod.liczba == 0:
        msg = "Brak towaru na stanie!"
        success = False
    else:
        msg = "Produkt nie istnieje."
        success = False
    
    session.close()
    return success, msg, paragon_info

def usun_produkt_calowicie(id_prod):
    session = get_session()
    prod = session.query(Produkt).filter_by(id=id_prod).first()
    raport = None
    if prod:
        # Raport likwidacyjny przed usunięciem
        wartosc_calkowita = prod.liczba * prod.cena
        raport = f"""
        RAPORT LIKWIDACJI:
        Produkt: {prod.nazwa}
        Usunięto sztuk: {prod.liczba}
        Strata wartości: {wartosc_calkowita:.2f} PLN
        """
        session.delete(prod)
        session.commit()
    session.close()
    return raport

# --- INTERFEJS ---

st.title("📊 Centrum Dowodzenia Magazynem")

session = get_session()
produkty_all = session.query(Produkt).all()
kategorie_all = session.query(Kategoria).all()
session.close()

# 1. DASHBOARD I WYKRESY (Nowość)
if produkty_all:
    # Konwersja do Pandas DataFrame dla łatwiejszej analizy
    data = []
    for p in produkty_all:
        kat_nazwa = next((k.nazwa for k in kategorie_all if k.id == p.kategoria_id), "Inne")
        data.append({
            "Nazwa": p.nazwa,
            "Ilość": p.liczba,
            "Cena": p.cena,
            "Wartość": p.liczba * p.cena,
            "Kategoria": kat_nazwa
        })
    df = pd.DataFrame(data)

    # Metryki na górze
    m1, m2, m3 = st.columns(3)
    m1.metric("Całkowita wartość magazynu", f"{df['Wartość'].sum():.2f} PLN")
    m2.metric("Liczba produktów (SKU)", len(df))
    m3.metric("Łączna liczba sztuk", df['Ilość'].sum())

    st.divider()
    
    # Wykresy w dwóch kolumnach
    c_chart1, c_chart2 = st.columns(2)
    
    with c_chart1:
        st.subheader("Stany magazynowe (Ilość)")
        # Wykres słupkowy: Produkt vs Ilość
        st.bar_chart(df.set_index("Nazwa")["Ilość"], color="#4CAF50") # Zielony

    with c_chart2:
        st.subheader("Wartość w kategoriach")
        # Agregacja wartości po kategoriach
        df_kat = df.groupby("Kategoria")["Wartość"].sum()
        st.bar_chart(df_kat, color="#FF9800") # Pomarańczowy

else:
    st.warning("Dodaj produkty, aby zobaczyć statystyki.")

st.divider()

# 2. ZARZĄDZANIE (Tabele i Akcje)
tab1, tab2 = st.tabs(["🛒 Lista i Sprzedaż", "⚙️ Edycja i Dodawanie"])

with tab1:
    st.header("Terminal Sprzedażowy")
    
    # Opcje stanu (Filtrowanie)
    filter_col, _ = st.columns([1,3])
    tylko_niskie = filter_col.checkbox("Pokaż tylko kończące się produkty (< 5 szt.)")
    
    if produkty_all:
        for p in produkty_all:
            # Filtr logiczny
            if tylko_niskie and p.liczba >= 5:
                continue

            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([1, 2, 1, 1])
                
                # Zdjęcie
                if p.zdjecie_url:
                    c1.image(p.zdjecie_url, width=80)
                else:
                    c1.write("📦")
                
                # Info
                c2.write(f"**{p.nazwa}**")
                # Kolorowanie stanu: Czerwony jak mało, Zielony jak dużo
                color = "red" if p.liczba < 5 else "green"
                c2.markdown(f"Stan: :{color}[**{p.liczba} szt.**] | Cena: {p.cena} PLN")
                
                # Przycisk SPRZEDAŻ (Generuje Paragon)
                if c3.button(f"Sprzedaj (1 szt)", key=f"sell_{p.id}"):
                    success, msg, paragon = sprzedaj_produkt(p.id)
                    if success:
                        st.toast("Sprzedano!", icon="💰")
                        # WYŚWIETLANIE PARAGONU (Alert)
                        st.success(f"""
                        🧾 **PARAGON FISKALNY (Symulacja)** --------------------------------  
                        Produkt: **{paragon['produkt']}** Cena: **{paragon['cena']:.2f} PLN** Data: {paragon['data']}  
                        --------------------------------  
                        _Dziękujemy za zakupy!_
                        """)
                        # Odśwież po 2 sekundach, żeby zaktualizować stan na ekranie
                        import time
                        time.sleep(2) 
                        st.rerun()
                    else:
                        st.error(msg)

                # Przycisk USUWANIE (Likwidacja)
                if c4.button("Usuń z bazy", key=f"del_{p.id}", type="primary"):
                    raport = usun_produkt_calowicie(p.id)
                    if raport:
                        st.warning(raport) # Wyświetla raport likwidacyjny
                        st.rerun()

    else:
        st.info("Magazyn jest pusty.")

with tab2:
    # Tu przenieśliśmy formularze dodawania (kod taki jak wcześniej, skrócony dla czytelności)
    st.write("Tu znajdują się formularze dodawania kategorii i produktów (jak w poprzedniej wersji).")
    # (Wklej tutaj kod formularzy z poprzedniej odpowiedzi, jeśli go potrzebujesz w pełni)
