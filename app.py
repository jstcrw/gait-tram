import requests
from bs4 import BeautifulSoup
from flask import Flask, jsonify, request, redirect, session, render_template_string
import os


app = Flask(__name__)

app.secret_key = "cos_losowego_do_sesji"
APP_PASSWORD = os.environ.get("APP_PASSWORD")

print("ENV KEYS:", list(os.environ.keys()))
print("APP_PASSWORD repr:", repr(APP_PASSWORD))



# Zmień na swoje prawdziwe dane
USERNAME = '3123'                  # Twój numer konta
PASSWORD = '446685923008'          # ← wpisz tutaj swoje prawdziwe hasło

LOGIN_HTML = """
<!doctype html>
<title>Logowanie</title>
<h3>Podaj hasło</h3>
<form method="post">
  <input type="password" name="password" autofocus>
  <button type="submit">Wejdź</button>
</form>
{% if error %}
<p style="color:red;">Złe hasło</p>
{% endif %}
"""

@app.route("/login", methods=["GET", "POST"])
def login():
    print("APP_PASSWORD =", APP_PASSWORD)

  
    if request.method == "POST":
        if request.form.get("password") == APP_PASSWORD:
            session["logged"] = True
            return redirect("/")
        else:
            return render_template_string(LOGIN_HTML, error=True)

    return render_template_string(LOGIN_HTML, error=False)



@app.route('/get_data')
def get_data():
    if not session.get("logged"):
        return jsonify({"error": "Brak dostępu"}), 403
    try:
        req_session = requests.Session()
        
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'pl-PL,pl;q=0.9',
            'Referer': 'https://tram.gait.pl/index.php',
            'Origin': 'https://tram.gait.pl',
        })

        url = 'https://tram.gait.pl/index.php'

        req_session.get(url)

        login_data = {
            'konto': USERNAME,
            'password': PASSWORD,
        }

        login_response = req_session.post(url, data=login_data, allow_redirects=True)

        if login_response.status_code != 200:
            return jsonify({'error': f'Błąd logowania – kod HTTP {login_response.status_code}'})

        soup = BeautifulSoup(login_response.text, 'html.parser')

        main_rows = []

        # Wyciągamy wiersze z głównej tabeli
        for table in soup.find_all('table'):
            if 'Data' in table.get_text(strip=True) and 'Nr służbowy' in table.get_text(strip=True):
                headers = None
                for tr in table.find_all('tr'):
                    cells = [td.get_text(strip=True) for td in tr.find_all(['td', 'th'])]
                    if not cells:
                        continue

                    if not headers and len(cells) >= 8 and 'Data' in cells[0]:
                        headers = cells
                        continue

                    if headers and len(cells) >= 6:
                        # Pomijamy wiersz z informacjami dodatkowymi
                        row_text = ' '.join(cells).lower()
                        if 'procedura narkotesty' in row_text or 'ulotka rekrutacyjna' in row_text:
                            continue
                        row = dict(zip(headers, cells + [''] * (len(headers) - len(cells))))
                        main_rows.append(row)

                break  # bierzemy tylko pierwszą pasującą tabelę

        # INFO – proste zebranie tekstu po tabeli (można później ulepszyć)
        info_html = '<p>Brak dodatkowych informacji lub sekcja nie została znaleziona.</p>'
        body_text = soup.get_text(separator='\n', strip=True)
        start = body_text.find('Procedura Narkotesty')
        if start != -1:
            info_html = '<pre>' + body_text[start:start+800] + '</pre>'

        return jsonify({
            'success': True,
            'main_rows': main_rows,
            'info_html': info_html,
            'main_count': len(main_rows)
        })

    except Exception as e:
        return jsonify({'error': f'Błąd serwera: {str(e)}'})

from flask import render_template_string

@app.route('/')
def home():
    if not session.get("logged"):
        return redirect("/login")
    return render_template_string('''
<!DOCTYPE html>
<html lang="pl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Wykaz służb – 3123</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
  <link rel="stylesheet" href="https://cdn.datatables.net/1.13.6/css/dataTables.bootstrap5.min.css">
  <style>
    body { padding: 20px; background: #f8f9fa; }
    h1 { color: #2b6777; }
    .table th { background: #2b6777; color: white; }
    .table td, th { text-align: center; vertical-align: middle; }
    .empty { color: #6c757d; font-style: italic; }
    .accordion-body { background: #fff; padding: 15px; border: 1px solid #dee2e6; border-radius: 0 0 6px 6px; }
    .dzisiejszy-wiersz { background-color: #c8d8e4 !important;   /* Bubblegum color */ }
    .dzisiejszy-wiersz td { background-color: inherit !important;   /* komórki dziedziczą kolor wiersza */ }
    .btn-primary { background-color: #2b6777 !important; }
  </style>
</head>
<body>
  <div class="container">
    <h1 class="mb-4">Wykaz służb – 3123 Justyński Marcin</h1>
    <p class="mb-3">Ostatnia aktualizacja: <span id="last-update">—</span></p>
    <button id="refresh-btn" class="btn btn-primary mb-4">Odśwież</button>

    <div class="table-responsive mb-5">
      <table id="tabela" class="table table-striped table-bordered table-hover">
        <thead>
          <tr>
            <th>Data</th>
            <th>Służba</th>
            <th>Początek służby</th>
            <th>Rozpoczęcie</th>
            <th>Zakończenie</th>
            <th>Koniec służby</th>
            <th>Czas trwania</th>
            <th>Uwagi</th>
          </tr>
        </thead>
        <tbody id="tbody"></tbody>
      </table>
    </div>

    <div class="accordion" id="infoAccordion">
      <div class="accordion-item">
        <h2 class="accordion-header">
          <button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#infoCollapse">
            Dodatkowe informacje (procedury, ulotki, linki itp.)
          </button>
        </h2>
        <div id="infoCollapse" class="accordion-collapse collapse" data-bs-parent="#infoAccordion">
          <div class="accordion-body" id="info-body">
            Ładowanie...
          </div>
        </div>
      </div>
    </div>
  </div>

<a href="/logout" class="btn btn-secondary mb-3">Wyloguj</a>


  <script src="https://code.jquery.com/jquery-3.7.1.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
  <script src="https://cdn.datatables.net/1.13.6/js/jquery.dataTables.min.js"></script>
  <script src="https://cdn.datatables.net/1.13.6/js/dataTables.bootstrap5.min.js"></script>

  <script>
    let tabela;

    async function loadData() {
      try {
       const r = await fetch('/get_data', {
  credentials: 'same-origin'
});

if (!r.ok) {
  alert('Sesja wygasła, odśwież stronę i zaloguj się ponownie');
  return;
}

const d = await r.json();


        const d = await r.json();
        if (!d.success) throw new Error(d.error || 'Brak danych');

        // Główna tabela
        const tbody = document.getElementById('tbody');
        tbody.innerHTML = '';

        d.main_rows.forEach(row => {
            const tr = document.createElement('tr');

            const dataWiersza = row.Data || '';
            const dzis = new Date().toISOString().slice(0, 10);  // np. "2026-02-06"

            if (dataWiersza === dzis) {
                tr.classList.add('dzisiejszy-wiersz');
            }

            [
                dataWiersza || '-',
                row.Służba || '-',
                row['Początek służby'] || '-',
                row['Godzina rozpoczęcia'].replace(/:00$/, '') || '-',
                row['Godzina zakończenia'].replace(/:00$/, '') || '-',
                row['Koniec służby'] || '-',
                row['Czas trwania'].replace(/:00$/, '') || '-',
                row.Uwagi || ''
            ].forEach(text => {
                const td = document.createElement('td');
                td.textContent = text;
                if (text === '-' || text === '00:00:00') td.classList.add('empty');
                tr.appendChild(td);
            });

            tbody.appendChild(tr);
        });

        // Sekcja INFO – wstawiamy surowy HTML (linki będą działać)
        document.getElementById('info-body').innerHTML = d.info_html;

        document.getElementById('last-update').textContent = new Date().toLocaleString('pl-PL');

        if (tabela) tabela.destroy();
        tabela = $('#tabela').DataTable({
          order: [[0, 'desc']],
          language: { url: 'https://cdn.datatables.net/plug-ins/1.13.6/i18n/pl.json' },
          pageLength: 25,
          lengthMenu: [10, 25, 50, 100, { label: 'Wszystko', value: -1 }]
        });

      } catch (e) {
        alert('Błąd: ' + e.message);
      }
    }

    loadData();
    setInterval(loadData, 300000);
    document.getElementById('refresh-btn').addEventListener('click', loadData);
  </script>
</body>
</html>
    ''')



if __name__ == '__main__':

    app.run(host='0.0.0.0', port=5000, debug=True)

@app.route("/logout")
def logout():
    req_session.clear()
    return redirect("/login")




