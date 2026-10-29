from django.core.exceptions import ValidationError
from django.test import TestCase

from .models import Emprestimo, Leitor, Livro


class BibliotecaTestCase(TestCase):
    def setUp(self):
        self.livro = Livro.objects.create(
            titulo="Dom Casmurro",
            autor="Machado de Assis",
            isbn="9780000000001",
            quantidade_total=2,
            quantidade_disponivel=2,
        )
        self.leitor = Leitor.objects.create(
            nome="Ana Leitora",
            email="ana@example.com",
        )

    def test_emprestimo_reduz_e_devolucao_restaura_estoque(self):
        emprestimo = Emprestimo.objects.create(livro=self.livro, leitor=self.leitor)

        self.livro.refresh_from_db()
        self.assertEqual(self.livro.quantidade_disponivel, 1)

        self.assertTrue(emprestimo.marcar_como_devolvido())
        self.assertFalse(emprestimo.marcar_como_devolvido())
        self.livro.refresh_from_db()
        self.assertEqual(self.livro.quantidade_disponivel, 2)

    def test_nao_permite_emprestimo_sem_exemplar_disponivel(self):
        self.livro.quantidade_disponivel = 0
        self.livro.save(update_fields=["quantidade_disponivel"])

        with self.assertRaises(ValidationError):
            Emprestimo.objects.create(livro=self.livro, leitor=self.leitor)

        self.assertEqual(Emprestimo.objects.count(), 0)

    def test_excluir_emprestimo_ativo_libera_exemplar(self):
        emprestimo = Emprestimo.objects.create(livro=self.livro, leitor=self.leitor)
        emprestimo.delete()

        self.livro.refresh_from_db()
        self.assertEqual(self.livro.quantidade_disponivel, 2)
