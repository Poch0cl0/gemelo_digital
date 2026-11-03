"""Browser integration checks: python -m unittest motor.test_exports (Playwright optional)."""
import csv
import io
import json
import struct
import tempfile
import threading
import unittest
from pathlib import Path
from motor.ui import make_server

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None


@unittest.skipUnless(sync_playwright, 'Install Playwright and Chromium for browser checks')
class ExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.server = make_server(0, Path(cls.temp.name) / 'test.sqlite3')
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        cls.temp.cleanup()

    def setUp(self):
        self.page = self.browser.new_page(accept_downloads=True)
        self.errors = []
        self.page.on('pageerror', lambda error: self.errors.append(str(error)))
        self.page.goto(f'http://127.0.0.1:{self.server.server_port}/simulator')
        self.page.locator('#patients tr').first.wait_for()
        from playwright.sync_api import expect
        expect(self.page.locator('#csv')).to_be_enabled()

    def tearDown(self):
        self.assertEqual(self.errors, [])
        self.page.close()

    def download(self, target, format):
        with self.page.expect_download() as event:
            self.page.evaluate('([selector, format]) => ScientificExport.exportTarget(document.querySelector(selector), format)', [target, format])
        return Path(event.value.path()).read_bytes()

    def test_filtered_csv_and_vector_and_png(self):
        self.page.select_option('#filter', '0')
        expected = self.page.evaluate("ScientificExport.data(document.querySelector('#patients').closest('table'))")
        payload = self.download('.patient-table table', 'csv').decode('utf-8-sig')
        rows = list(csv.reader(io.StringIO(payload)))
        self.assertEqual(len(rows) - 1, len(expected['rows']))
        self.assertTrue(all(r[1] == 'P0' for r in rows[1:]))
        self.assertEqual([r[2] for r in rows[1:]], [str(r[2]) for r in expected['rows']])
        svg = self.download('#chart > svg', 'svg').decode()
        self.assertIn('Tiempo (min)', svg)
        self.assertIn('Pacientes (personas)', svg)
        self.assertIn('8px', svg)
        self.assertNotIn('<button', svg)
        self.assertNotIn('export-tools', svg)
        png = self.download('#chart > svg', 'png')
        self.assertEqual(png[:8], b'\x89PNG\r\n\x1a\n')
        width, height = struct.unpack('>II', png[16:24])
        self.assertGreaterEqual(width, 2126)
        self.assertGreater(height, 500)
        offset, phys = 8, []
        while offset < len(png):
            size = struct.unpack('>I', png[offset:offset+4])[0]
            if png[offset+4:offset+8] == b'pHYs':
                phys.append(struct.unpack('>IIB', png[offset+8:offset+17]))
            offset += size + 12
        self.assertEqual(phys, [(11811, 11811, 1)])

    def test_pdf_preview_and_empty_data(self):
        with self.page.expect_popup() as popup:
            self.page.evaluate("ScientificExport.exportTarget(document.querySelector('#chart > svg'), 'pdf')")
        preview = popup.value
        preview.wait_for_selector('#figures svg')
        self.assertIn('Evolución de pacientes', preview.locator('#figures').text_content())
        pdf = preview.pdf()
        self.assertTrue(pdf.startswith(b'%PDF'))
        preview.close()
        self.page.fill('#demand', '0')
        self.page.click('#run')
        from playwright.sync_api import expect
        expect(self.page.locator('#patient-count')).to_have_text('0 pacientes · Tiempos en minutos')
        rows = list(csv.reader(io.StringIO(self.download('.patient-table table', 'csv').decode('utf-8-sig'))))
        self.assertEqual(len(rows), 1)

    def test_ml_and_operational_pagination(self):
        self.page.goto(f'http://127.0.0.1:{self.server.server_port}/ml')
        self.page.locator('[data-tab="eda"]').click()
        self.page.wait_for_selector('svg.ml-chart')
        self.download('svg.ml-chart', 'svg')
        for tab in ['business', 'preparation', 'cv', 'tuning', 'selection', 'test', 'explain']:
            self.page.locator(f'[data-tab="{tab}"]').click()
            self.assertEqual(self.page.locator('#ml-content .error-box').count(), 0, tab)
        self.page.goto(f'http://127.0.0.1:{self.server.server_port}/operations')
        self.page.locator('#record-body tr').first.wait_for()
        self.page.evaluate('''async () => {
          for(let i=0;i<15;i++) {
            const response=await fetch('/api/ops/areas',{method:'POST',headers:{'Content-Type':'application/json'},
              body:JSON.stringify({code:'EXPORT-'+i,name:'Export test '+i,kind:'support',active:true})});
            if(!response.ok)throw new Error(await response.text());
          }
        }''')
        self.page.click('#refresh')
        from playwright.sync_api import expect
        expect(self.page.locator('#refresh')).to_be_enabled()
        meta = self.page.evaluate("ScientificExport.data(document.querySelector('table'))")
        self.assertGreater(len(meta['rows']), 10)
        self.assertLessEqual(self.page.locator('#record-body tr').count(), 10)
        rows = list(csv.reader(io.StringIO(self.download('table', 'csv').decode('utf-8-sig'))))
        self.assertEqual(len(rows) - 1, len(meta['rows']))
        self.assertNotIn('Acciones', rows[0])
        self.assertEqual(meta['source'], '/api/ops/areas')

    def test_table_sort_and_filter_match_export(self):
        tools = self.page.locator('.patient-table .export-tools')
        tools.locator('select[aria-label="Ordenar tabla"]').select_option('2:-1')
        tools.locator('input[type="search"]').fill('P0')
        actual = self.page.evaluate("ScientificExport.data(document.querySelector('#patients').closest('table')).rows")
        self.assertTrue(all(row[1] == 'P0' for row in actual))
        self.assertEqual([r[2] for r in actual], sorted([r[2] for r in actual], reverse=True))
        payload = list(csv.reader(io.StringIO(self.download('.patient-table table', 'csv').decode('utf-8-sig'))))
        self.assertEqual(len(payload)-1, len(actual))
        self.assertEqual(self.page.locator('#patients tr').count(), len(actual))

    def test_large_table_wrapping_sorting_and_precision(self):
        # Generated fixtures are confined to tests; no application data is replaced.
        result = self.page.evaluate(r'''() => {
          const table=document.createElement('table');
          table.innerHTML='<thead><tr><th>Valor (min)</th><th>Identificador</th></tr></thead><tbody></tbody>';
          document.body.append(table);
          const rows=Array.from({length:10000},(_,i)=>[i+0.123456789, 'x'.repeat(220)+i]);
          ScientificExport.register(table,()=>({title:'Prueba',headers:['Valor (min)','Identificador'],rows,notes:[],source:'test'}));
          const meta=ScientificExport.data(table);
          const figure=ScientificExport.figure(table,meta,rows.slice(0,25));
          document.body.append(figure);
          const bounds=figure.getBBox(), box=figure.viewBox.baseVal;
          const csv=ScientificExport.csv(meta.headers,meta.rows);
          const safe=ScientificExport.csv(['Texto'],[['=1+1'],[-2.5],['a,"b"\nfin']]);
          figure.remove();
          return {count:meta.rows.length,original:rows[0][0],csvFirst:csv.split('\r\n')[1],safe,
            fits:bounds.x>=0 && bounds.y>=0 && bounds.x+bounds.width<=box.width+1 && bounds.y+bounds.height<=box.height+1};
        }''')
        self.assertEqual(result['count'], 10000)
        self.assertIn('0.123456789', result['csvFirst'])
        self.assertTrue(result['fits'])
        self.assertIn("'=1+1", result['safe'])
        self.assertIn('"-2.5"', result['safe'])
        self.page.evaluate('''() => {
          const table=document.querySelector('body > table'); table.id='large-export';
          ScientificExport.register(table,()=>({title:'Paginación',headers:['Índice','Valor (min)'],
            rows:Array.from({length:70},(_,i)=>[i,i+0.123456789]),notes:[],source:'test'}));
        }''')
        with self.page.expect_popup() as event:
            self.page.evaluate("ScientificExport.exportTarget(document.querySelector('#large-export'),'pdf')")
        preview = event.value
        preview.wait_for_selector('#figures svg')
        counts = preview.locator('#figures svg metadata').evaluate_all('(nodes)=>nodes.map(n=>JSON.parse(n.textContent).rows.length)')
        self.assertGreaterEqual(len(counts), 3)
        self.assertEqual(sum(counts), 70)
        preview.close()


if __name__ == '__main__':
    unittest.main()
