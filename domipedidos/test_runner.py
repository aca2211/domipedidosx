from unittest import mock

from django.test.runner import DiscoverRunner

from menu.models import Sede


class RunnerConSedesAbiertas(DiscoverRunner):
    """Las pruebas no dependen de la hora real (HU47).

    Por defecto toda sede está abierta; una prueba que necesite una sede
    cerrada lo declara con mock.patch.object(Sede, 'is_open_now', return_value=False).
    """

    def run_tests(self, *args, **kwargs):
        with mock.patch.object(Sede, 'is_open_now', return_value=True):
            return super().run_tests(*args, **kwargs)
