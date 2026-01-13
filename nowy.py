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
