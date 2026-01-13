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
