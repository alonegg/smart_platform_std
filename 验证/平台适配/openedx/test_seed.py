from pathlib import Path
import subprocess
import sys
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent


class SeedInputTest(unittest.TestCase):
    def test_two_run_templates_and_required_blocks(self):
        template = (ROOT / 'course-template.xml').read_text(encoding='utf-8')
        for run in ('run01', 'run02'):
            course = ET.fromstring(template.replace('__RUN__', run))
            self.assertEqual(course.attrib['url_name'], run)
            self.assertEqual(course.attrib['org'], 'SYNTH')
            self.assertEqual(len(course.findall('.//video')), 1)
            self.assertEqual(course.find('.//video/source').attrib['src'], '/static/synthetic.mp4')
            self.assertEqual(course.find('.//video').attrib['youtube'], '1.00:')
            self.assertEqual(len(course.findall('.//problem/numericalresponse')), 1)
            self.assertEqual(len(course.findall('.//openassessment')), 1)
            self.assertEqual(course.find('.//openassessment/assessments/assessment').attrib['name'], 'staff-assessment')

    def test_missing_and_unknown_stage_refused(self):
        for args in ([], ['--stage', 'unknown']):
            result = subprocess.run([sys.executable, str(ROOT / 'seed.py'), *args], capture_output=True)
            self.assertEqual(result.returncode, 2)


if __name__ == '__main__':
    unittest.main()
