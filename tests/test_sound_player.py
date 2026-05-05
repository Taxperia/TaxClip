import unittest
from unittest.mock import patch

import clipstack.sound_player as sound_player


class SoundPlayerTests(unittest.TestCase):
    def test_sound_player_raises_when_runtime_backend_is_unavailable(self):
        with patch.object(sound_player, "_probe_runtime_backend", return_value=False):
            with patch.object(sound_player, "_LAST_BACKEND_ERROR", "Not available"):
                with self.assertRaises(RuntimeError) as ctx:
                    sound_player.SoundPlayer()

        self.assertIn("Not available", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
