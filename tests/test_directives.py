import json
import os
import tempfile
import unittest

from mock import (
    MagicMock,
    Mock,
)


class TestDumbList(unittest.TestCase):
    """Test that new smoketest is compatible with old smoketest files.
    """

    def test_include_directive(self):
        from smoketest.directives import FileParser
        filename = 'static.txt'
        line = '#include %s' % filename
        options = Mock()
        directive = FileParser(filename, options)._get_directive_from_dumb_list_line(line)
        self.assertTrue(directive.filename.endswith(filename))

    def test_redirect_with_target(self):
        from smoketest.directives import FileParser
        url = 'http://www.usnews.com/congress/platts-todd'
        redirect_to = 'http://www.usnews.com/topics/people/todd_russell_platts'
        line = '30X %s -> %s' % (url, redirect_to)
        options = Mock()
        options.scheme = None
        options.level = 'stag'
        options.port = None
        options.cachebust = False
        directive = FileParser(None, options)._get_directive_from_dumb_list_line(line)

        # Expect one redirect test to be on the directive. Redirect-to URL
        # should respect level.
        self.assertEqual(len(directive.tests), 1)
        test = directive.tests[0]
        self.assertEqual(test.target_code, '30X')
        self.assertEqual(
            test.target_location,
            redirect_to.replace('www.', 'www-stag.')
        )

    def test_environment_specific_status_code_live(self):
        from smoketest.directives import FileParser
        url = 'http://premium.usnews.com/best-colleges/rankings/national-universities'
        line = '30X_live %s' % url
        options = Mock()
        options.scheme = None
        options.level = 'live'
        directive = FileParser(None, options)._get_directive_from_dumb_list_line(line)

        # Expect one 30X status test on the directive
        self.assertEqual(len(directive.tests), 1)
        test = directive.tests[0]
        self.assertEqual(test.target_code, '30X')

    def test_environment_specific_status_code_not_live(self):
        from smoketest.directives import FileParser
        url = 'http://premium.usnews.com/best-colleges/rankings/national-universities'
        line = '30X_live %s' % url
        options = Mock()
        options.scheme = None
        options.level = 'stag'
        directive = FileParser(None, options)._get_directive_from_dumb_list_line(line)

        # Expect one 200 status test on the directive
        self.assertEqual(len(directive.tests), 1)
        test = directive.tests[0]
        self.assertEqual(test.target_code, '200')


class TestFileParser(unittest.TestCase):
    """Test that smoketest is correctly parsing the files
    """

    def _create_file(self, extension):
        f = tempfile.NamedTemporaryFile(
            mode='w',
            suffix=extension,
            delete=False,
        )
        self._temporary_files.append(f)
        return f

    def setUp(self):
        self._temporary_files = []

    def tearDown(self):
        for f in self._temporary_files:
            os.unlink(f.name)

    def test_generate_directives_only_levels(self):
        from smoketest.directives import FileParser

        json_file = self._create_file('.json')
        json_file.write(json.dumps([
            {
                'directive': 'check',
                'url': 'www.mock.com'
            },
            {
                'directive': 'check',
                'url': 'www.mock.com',
                'only_levels': ['live']
            },
            {
                'directive': 'check',
                'url': 'www.mock.com',
                'only_levels': ['stag', 'live']
            },
        ]))
        json_file.close()

        # uat1 level should only pick up the first directive
        options = Mock()
        options.scheme = None
        options.level = 'uat1'
        file_parser = FileParser(json_file.name, options)
        directives = list(file_parser.generate_directives())
        self.assertEquals(len(directives), 1)

        # stag level should pick up the first and third directives
        FileParser._visited_files = set()
        options = Mock()
        options.scheme = None
        options.level = 'stag'
        file_parser = FileParser(json_file.name, options)
        directives = list(file_parser.generate_directives())
        self.assertEquals(len(directives), 2)

        # live level should pick up all three directives
        FileParser._visited_files = set()
        options = Mock()
        options.scheme = None
        options.level = 'live'
        file_parser = FileParser(json_file.name, options)
        directives = list(file_parser.generate_directives())
        self.assertEquals(len(directives), 3)

    def test_generate_directives_only_levels_works_with_include(self):
        from smoketest.directives import FileParser

        yaml_file = self._create_file('.yaml')
        yaml_file.write('- https://www.usnews.com')
        yaml_file.close()

        json_file = self._create_file('.json')
        json_file.write(json.dumps([
            {
                'directive': 'include',
                'filename': yaml_file.name,
                'only_levels': ['uat1']
            },
        ]))
        json_file.close()

        # live level should not pick up the directive
        options = Mock()
        options.scheme = None
        options.level = 'live'
        file_parser = FileParser(json_file.name, options)
        directives = list(file_parser.generate_directives())
        self.assertEquals(len(directives), 0)

        # uat1 level should pick up the directive
        FileParser._visited_files = set()
        options = Mock()
        options.scheme = None
        options.level = 'uat1'
        file_parser = FileParser(json_file.name, options)
        directives = list(file_parser.generate_directives())
        self.assertEquals(len(directives), 1)

    def test_generate_directives_only_levels_is_not_a_list(self):
        from smoketest.directives import FileParser

        json_file = self._create_file('.json')
        json_file.write(json.dumps([
            {
                'directive': 'check',
                'url': 'example.com',
                'only_levels': 'string!'
            },
        ]))
        json_file.close()

        options = Mock()
        options.scheme = None
        options.level = 'uat1'
        fileparser = FileParser(json_file.name, options)
        self.assertRaises(
            Exception,
            next,
            fileparser.generate_directives(),
        )

    def test_generate_directives_from_nonexistent_file(self):
        from smoketest.directives import (
            InputFileError,
            generate_directives_from_file,
        )
        self.assertRaises(
            InputFileError,
            next,
            generate_directives_from_file('fake.txt', None)
        )

        self.assertRaises(
            InputFileError,
            next,
            generate_directives_from_file('fake.yaml', None),
        )

    def test_generate_directives_from_invalid_yaml_file(self):
        from smoketest.directives import (
            InputFileError,
            generate_directives_from_file,
        )
        invalid_yaml_file = self._create_file('.yaml')
        invalid_yaml_file.write('key: -')
        invalid_yaml_file.close()

        self.assertRaises(
            InputFileError,
            next,
            generate_directives_from_file(invalid_yaml_file.name, None)
        )

    def test_generate_directives_from_invalid_json_file(self):
        from smoketest.directives import (
            InputFileError,
            generate_directives_from_file,
        )
        invalid_json_file = self._create_file('.json')
        invalid_json_file.write('x')
        invalid_json_file.close()

        self.assertRaises(
            InputFileError,
            next,
            generate_directives_from_file(invalid_json_file.name, None)
        )


class TestDirectives(unittest.TestCase):
    """Tests for the Directive classes and related functions.
    """

    def test_get_urls_from_element_with_url_list(self):
        from smoketest.directives import get_urls_from_element
        options = Mock()
        options.scheme = None
        options.port = ''
        options.level = 'live'
        options.cachebust = False
        elem = {
            "urls": [
                "http://www.usnews.com",
                "http://www.indeed.com",
            ],
            "status": "404",
        }
        expected = [
            "http://www.usnews.com",
            "http://www.indeed.com",
        ]
        actual = get_urls_from_element(elem, options)
        self.assertEqual(expected, actual)

    def test_get_urls_from_flat_url(self):
        from smoketest.directives import get_urls_from_element
        options = Mock()
        options.scheme = None
        options.port = '8999'
        options.level = 'stag'
        options.cachebust = False
        elem = {
            'url': 'http://www.usnews.com',
        }
        results = get_urls_from_element(elem, options)
        self.assertEqual(results[0], 'http://www-stag.usnews.com:8999')
        self.assertEqual(len(results), 1)

    def test_urls_from_dict_of_urls_use_non_other(self):
        from smoketest.directives import get_urls_from_element
        options = Mock()
        options.port = '8999'
        options.level = 'stag'
        options.cachebust = True
        elem = {
            'url': {
                'stag': 'usnews.com',
                'other': 'google.com',
            }
        }
        results = get_urls_from_element(elem, options)

        # Notice that it should not be cachebusted.
        self.assertEqual(results[0], 'usnews.com')
        self.assertEqual(len(results), 1)

    def test_urls_from_dict_of_urls_use_other(self):
        from smoketest.directives import get_urls_from_element
        options = Mock()
        options.scheme = None
        options.port = '8999'
        options.level = 'sand14'
        options.cachebust = False
        elem = {
            'url': {
                'stag': 'http://www.usnews.com',
                'other': 'http://www.google.com',
            }
        }
        results = get_urls_from_element(elem, options)
        self.assertEqual(results[0], 'http://www-sand14.google.com:8999')
        self.assertEqual(len(results), 1)

    def test_get_response(self):
        from smoketest.directives import CheckDirective
        from smoketest.settings import get_ca_path
        elem = {
            'url': 'http://www.usnews.com',
        }
        options = Mock()
        options.scheme = None
        options.port = '8999'
        options.level = 'sand14'
        options.cachebust = False
        options.dry_run = False
        directive = CheckDirective(elem, options)
        directive.session = Mock()

        url = 'http://www.usnews.com'
        extra_headers = {'a': 'b'}
        response = directive.get_response(url, extra_headers)
        directive.session.get.assert_called_once_with(
            url,
            verify=get_ca_path(),
            allow_redirects=False,
            timeout=directive.timeout,
            headers=extra_headers
        )
        self.assertEqual(response, directive.session.get.return_value)

    def test_run(self):
        from smoketest.directives import CheckDirective
        elem = {
            'url': 'http://www.usnews.com',
        }
        options = Mock()
        options.scheme = None
        options.port = '8999'
        options.level = 'sand14'
        options.cachebust = False
        options.dry_run = False
        directive = CheckDirective(elem, options)
        directive._run_for_platform = MagicMock()
        directive.platforms = [
            Mock(),
            Mock(),
        ]
        directive.run()
        directive._run_for_platform.assert_any_calls(
            directive.platforms[0],
        )
        directive._run_for_platform.assert_any_calls(
            directive.platforms[1],
        )

    def test_run_for_platform(self):
        from smoketest.directives import CheckDirective

        platform = Mock()
        platform.headers = {'X-Test-Header': 'some-value'}
        elem = {
            'url': 'http://www.usnews.com',
        }
        options = Mock()
        options.scheme = None
        options.port = ''
        options.level = 'live'
        options.cachebust = False
        options.dry_run = False
        directive = CheckDirective(elem, options)
        directive.tests = []
        directive.get_response = MagicMock()
        directive._run_for_platform(platform)
        directive.get_response.assert_called_once_with(
            'http://www.usnews.com',
            platform.headers,
        )


class TestOptions(unittest.TestCase):
    """Tests related to ensuring that various options are available and
    respected.
    """

    def test_user_agent(self):
        from smoketest.directives import get_session
        from collections import namedtuple
        Options = namedtuple('Options', ('user_agent', 'dry_run'))

        elem = {'url': 'usnews.com'}
        options = Options('my user agent', False)
        session = get_session(elem, options)
        self.assertIn('User-Agent', session.headers)
        self.assertEqual(session.headers['User-Agent'], options.user_agent)
