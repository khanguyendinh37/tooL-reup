import unittest

from license_build_config import license_config_from_env

KEY = "ab" * 32


class LicenseBuildConfigTests(unittest.TestCase):
    def test_valid_env_produces_config(self):
        config = license_config_from_env({
            "VIDEODUB_LICENSE_ACCOUNT": "acct", "VIDEODUB_LICENSE_PUBLIC_KEY": KEY.upper(),
            "VIDEODUB_LICENSE_CONTACT": "Zalo 0900",
        })
        self.assertEqual(config["public_key"], KEY)
        self.assertEqual(config["api_url"], "https://api.keygen.sh")
        self.assertEqual(config["contact"], "Zalo 0900")

    def test_missing_or_bad_values_fail_the_build(self):
        for env in ({}, {"VIDEODUB_LICENSE_ACCOUNT": "a", "VIDEODUB_LICENSE_PUBLIC_KEY": "short"},
                    {"VIDEODUB_LICENSE_ACCOUNT": "a", "VIDEODUB_LICENSE_PUBLIC_KEY": KEY,
                     "VIDEODUB_LICENSE_API_URL": "http://insecure"}):
            with self.assertRaises(SystemExit):
                license_config_from_env(env)


if __name__ == "__main__":
    unittest.main()
