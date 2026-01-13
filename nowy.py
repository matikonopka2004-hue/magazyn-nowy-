import streamlit as st
import pandas as pd
import altair as alt
from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, Text
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from datetime import datetime
import time

# --- 1. KONFIGURACJA STRONY ---
st.set_page_config(page_title="Magazyn Pro v4", layout="wide")

# --- 2. BAZA DANYCH ---
Base = declarative_base()

class Kategoria(Base):
    __tablename__ = 'kategorie'
    id = Column(Integer, primary_key=True)
    nazwa = Column(String, nullable=False)
    opis = Column(Text)
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
DATABASE_URL = "sqlite:///magazyn_fixed.db"
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

# ZMODYFIKOWANA FUNKCJA: Obsługa ilości
def sprzedaj_produkt(id_prod, ilosc=1):
    with get_session() as session:
        prod = session.query(Produkt).filter_by(id=id_prod).first()
        
        if not prod:
            return False, "Błąd produktu", None

        if prod.liczba < ilosc:
             return False, f"⛔ Za mało towaru! Chcesz sprzedać {ilosc}, a masz {prod.liczba}.", None

        # Logika sprzedaży
        prod.liczba -= ilosc
        wartosc_transakcji = prod.cena * ilosc
        
        info = {
            "produkt": prod.nazwa,
            "ilosc": ilosc,
            "cena_jedn": prod.cena,
            "suma": wartosc_transakcji,
            "data": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        session.commit()
        return True, "Sprzedano", info

# ZMODYFIKOWANA FUNKCJA: Usuwanie (Korekta) ilości
def zdejmij_stan(id_prod, ilosc_do_usuniecia):
    with get_session() as session:
        prod = session.query(Produkt).filter_by(id=id_prod).first()
        if not prod:
            return False, "Produkt nie istnieje."
        
        if ilosc_do_usuniecia <= 0:
            return False, "Ilość musi być większa od 0."
            
        if prod.liczba < ilosc_do_usuniecia:
            return False, f"⛔ Nie możesz usunąć {ilosc_do_usuniecia} szt., masz tylko {prod.liczba}."
        
        prod.liczba -= ilosc_do_usuniecia
        session.commit()
        return True, f"📉 Skorygowano stan. Zdjęto {ilosc_do_usuniecia} szt."

def usun_produkt_calowicie(id_prod):
    with get_session() as session:
        prod = session.query(Produkt).filter_by(id=id_prod).first()
        if prod:
            wartosc = prod.liczba * prod.cena
            nazwa = prod.nazwa
            session.delete(prod)
            session.commit()
            return f"Usunięto kartotekę: {nazwa} (Strata całkowita: {wartosc:.2f} PLN)"
    return None

# --- 4. BEZPIECZNE POBIERANIE DANYCH ---
safe_products = []
safe_categories = {} 

with get_session() as session:
    kats = session.query(Kategoria).all()
    prods = session.query(Produkt).all()
    for k in kats:
        safe_categories[k.id] = k.nazwa
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

if safe_products:
    df = pd.DataFrame(safe_products)
    
    m1, m2, m3 = st.columns(3)
    m1.metric("Wartość magazynu", f"{df['wartosc'].sum():.2f} PLN")
    m2.metric("Liczba produktów (SKU)", len(df))
    m3.metric("Łącznie sztuk", df['liczba'].sum())
    
    st.divider()
    
    c1, c2 = st.columns(2)
    
    with c1:
        st.subheader("Stany Magazynowe")
        chart_qty = alt.Chart(df).mark_bar().encode(
            x=alt.X('nazwa', title='Produkt', sort=None),
            y=alt.Y('liczba', title='Ilość sztuk'),
            color=alt.Color('nazwa', legend=None),
            tooltip=['nazwa', 'liczba', 'kategoria_nazwa']
        ).interactive()
        st.altair_chart(chart_qty, use_container_width=True)

    with c2:
        st.subheader("Wartość w kategoriach")
        df_cat = df.groupby("kategoria_nazwa")["wartosc"].sum().reset_index()
        chart_val = alt.Chart(df_cat).mark_bar().encode(
            x=alt.X('kategoria_nazwa', title='Kategoria'),
            y=alt.Y('wartosc', title='Wartość (PLN)'),
            color=alt.Color('kategoria_nazwa', scale=alt.Scale(scheme='spectral')),
            tooltip=['kategoria_nazwa', 'wartosc']
        ).interactive()
        st.altair_chart(chart_val, use_container_width=True)

else:
    st.info("👋 Magazyn pusty. Dodaj produkty.")

st.divider()

# --- 6. ZAKŁADKI ---
tab1, tab2 = st.tabs(["🛒 Lista i Operacje", "➕ Dodawanie i Edycja"])

# ZAKŁADKA 1: LISTA I OPERACJE
with tab1:
    st.header("Zarządzanie Stanem")
    
    col_filt, _ = st.columns([2,3])
    alarm_mode = col_filt.checkbox("Tylko stany alarmowe (< 5 szt.)")

    if safe_products:
        for p in safe_products:
            if alarm_mode and p['liczba'] >= 5:
                continue

            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([1, 3, 1, 1])
                
                # Zdjęcie
                if p['zdjecie_url']:
                    c1.image(p['zdjecie_url'], width=80)
                else:
                    c1.markdown("📦")
                
                # Info
                c2.subheader(p['nazwa'])
                kolor = "red" if p['liczba'] < 5 else "green"
                c2.caption(f"Kategoria: {p['kategoria_nazwa']}")
                c2.markdown(f"Stan: :{kolor}[**{p['liczba']}**] | Cena: **{p['cena']:.2f} PLN**")
                
                # Przycisk SZYBKA SPRZEDAŻ (1 szt)
                if c3.button("⚡ Szybka sprzedaż (1)", key=f"sell_one_{p['id']}", use_container_width=True):
                    ok, msg, kwit = sprzedaj_produkt(p['id'], 1)
                    if ok:
                        st.toast("Sprzedano 1 szt.", icon="✅")
                        st.success(f"🧾 PARAGON: {kwit['produkt']} (1 szt) - {kwit['suma']:.2f} PLN")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(msg)
                
                # Przycisk USUŃ CAŁKOWICIE
                if c4.button("🗑️ Usuń kartotekę", key=f"del_db_{p['id']}", type="primary", use_container_width=True):
                    raport = usun_produkt_calowicie(p['id'])
                    st.warning(raport)
                    time.sleep(2)
                    st.rerun()

                # --- NOWOŚĆ: PANEL OPERACJI MASOWYCH ---
                with st.expander(f"🛠️ Operacje masowe (Sprzedaj / Usuń wiele sztuk) - {p['nazwa']}"):
                    st.write("Wybierz ilość i akcję:")
                    
                    # Kolumny wewnątrz expandera
                    ec1, ec2, ec3 = st.columns([1, 1, 1])
                    
                    # 1. Wybór ilości (Input)
                    # Ustawiamy max_value na aktualny stan magazynowy
                    max_val = p['liczba'] if p['liczba'] > 0 else 1
                    ilosc_input = ec1.number_input("Ilość", min_value=1, max_value=max_val, step=1, key=f"qty_{p['id']}")
                    
                    # 2. Przycisk SPRZEDAJ WIELE
                    if ec2.button(f"💰 Sprzedaj ({ilosc_input})", key=f"sell_multi_{p['id']}", use_container_width=True):
                        ok, msg, kwit = sprzedaj_produkt(p['id'], ilosc_input)
                        if ok:
                            st.balloons()
                            st.success(f"""
                            🧾 **PARAGON ZBIORCZY** Produkt: {kwit['produkt']}  
                            Ilość: {kwit['ilosc']} szt.  
                            Razem do zapłaty: **{kwit['suma']:.2f} PLN**
                            """)
                            time.sleep(2.5)
                            st.rerun()
                        else:
                            st.error(msg)
                            
                    # 3. Przycisk ZDEJMIJ ZE STANU (Korekta)
                    if ec3.button(f"📉 Zdejmij ({ilosc_input})", key=f"remove_multi_{p['id']}", use_container_width=True):
                        ok, msg = zdejmij_stan(p['id'], ilosc_input)
                        if ok:
                            st.warning(f"⚠️ {msg}")
                            time.sleep(1.5)
                            st.rerun()
                        else:
                            st.error(msg)
    else:
        st.write("Brak produktów.")

# ZAKŁADKA 2: DODAWANIE (Bez zmian)
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
                else: st.error("Podaj nazwę.")
        
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
                mapa_nazw = {v: k for k, v in safe_categories.items()}
                wybor_kat = st.selectbox("Kategoria", list(mapa_nazw.keys()))
                n_url = st.text_input("Zdjęcie URL (opcjonalnie)")
                
                if st.form_submit_button("Dodaj Produkt"):
                    if n_prod:
                        dodaj_produkt(n_prod, n_ilosc, n_cena, mapa_nazw[wybor_kat], n_url)
                        st.success("Dodano produkt!")
                        st.rerun()
                    else: st.error("Podaj nazwę!")
