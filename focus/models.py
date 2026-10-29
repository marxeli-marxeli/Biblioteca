from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone


def data_prevista_devolucao():
    """Define o prazo inicial do empréstimo em duas semanas."""
    return timezone.localdate() + timedelta(days=14)


class Livro(models.Model):
    titulo = models.CharField("título", max_length=200)
    autor = models.CharField(max_length=150)
    isbn = models.CharField("ISBN", max_length=20, unique=True)
    quantidade_total = models.PositiveSmallIntegerField("exemplares totais", default=1)
    quantidade_disponivel = models.PositiveSmallIntegerField(
        "exemplares disponíveis", default=1
    )

    class Meta:
        ordering = ["titulo"]
        verbose_name = "livro"
        verbose_name_plural = "livros"

    def __str__(self):
        return f"{self.titulo} — {self.autor}"

    def clean(self):
        # Impede que o estoque disponível ultrapasse o total cadastrado.
        if self.quantidade_disponivel > self.quantidade_total:
            raise ValidationError(
                {
                    "quantidade_disponivel": (
                        "A quantidade disponível não pode superar o total de exemplares."
                    )
                }
            )


class Leitor(models.Model):
    nome = models.CharField(max_length=150)
    email = models.EmailField("e-mail", unique=True)
    telefone = models.CharField(max_length=30, blank=True)
    cadastrado_em = models.DateTimeField("cadastrado em", auto_now_add=True)

    class Meta:
        ordering = ["nome"]
        verbose_name = "leitor"
        verbose_name_plural = "leitores"

    def __str__(self):
        return self.nome


class Emprestimo(models.Model):
    livro = models.ForeignKey(
        Livro, on_delete=models.PROTECT, related_name="emprestimos"
    )
    leitor = models.ForeignKey(
        Leitor, on_delete=models.PROTECT, related_name="emprestimos"
    )
    data_emprestimo = models.DateField("data do empréstimo", default=timezone.localdate)
    data_prevista = models.DateField(
        "devolução prevista", default=data_prevista_devolucao
    )
    devolvido_em = models.DateTimeField("devolvido em", null=True, blank=True)

    class Meta:
        ordering = ["-data_emprestimo"]
        verbose_name = "empréstimo"
        verbose_name_plural = "empréstimos"

    def __str__(self):
        return f"{self.livro} — {self.leitor}"

    def save(self, *args, **kwargs):
        # Um novo empréstimo reserva um exemplar dentro da mesma transação.
        if self._state.adding:
            if self.devolvido_em is not None:
                raise ValidationError(
                    "Um empréstimo novo não pode começar como já devolvido."
                )
            with transaction.atomic():
                livro = Livro.objects.select_for_update().get(pk=self.livro_id)
                if livro.quantidade_disponivel < 1:
                    raise ValidationError(
                        {"livro": "Não há exemplares disponíveis deste livro."}
                    )
                livro.quantidade_disponivel -= 1
                livro.save(update_fields=["quantidade_disponivel"])
                return super().save(*args, **kwargs)

        # Mantém o histórico consistente: livro e leitor não mudam após o cadastro.
        emprestimo_original = type(self).objects.only("livro_id", "leitor_id").get(
            pk=self.pk
        )
        if (
            emprestimo_original.livro_id != self.livro_id
            or emprestimo_original.leitor_id != self.leitor_id
        ):
            raise ValidationError(
                "Não é possível trocar o livro ou o leitor do empréstimo."
            )
        return super().save(*args, **kwargs)

    def marcar_como_devolvido(self):
        """Registra a devolução e devolve uma única vez o exemplar ao estoque."""
        if not self.pk:
            raise ValidationError("Salve o empréstimo antes de registrar a devolução.")

        with transaction.atomic():
            emprestimo = type(self).objects.select_for_update().get(pk=self.pk)
            if emprestimo.devolvido_em is not None:
                self.devolvido_em = emprestimo.devolvido_em
                return False

            livro = Livro.objects.select_for_update().get(pk=emprestimo.livro_id)
            if livro.quantidade_disponivel >= livro.quantidade_total:
                raise ValidationError(
                    "O estoque já está completo; verifique os dados do empréstimo."
                )
            livro.quantidade_disponivel += 1
            livro.save(update_fields=["quantidade_disponivel"])

            emprestimo.devolvido_em = timezone.now()
            emprestimo.save(update_fields=["devolvido_em"])
            self.devolvido_em = emprestimo.devolvido_em
            return True

    def delete(self, *args, **kwargs):
        # Apagar um empréstimo ainda ativo também libera o exemplar reservado.
        if not self.pk:
            return super().delete(*args, **kwargs)

        with transaction.atomic():
            emprestimo = type(self).objects.select_for_update().get(pk=self.pk)
            if emprestimo.devolvido_em is None:
                livro = Livro.objects.select_for_update().get(pk=emprestimo.livro_id)
                if livro.quantidade_disponivel >= livro.quantidade_total:
                    raise ValidationError(
                        "O estoque já está completo; verifique os dados do empréstimo."
                    )
                livro.quantidade_disponivel += 1
                livro.save(update_fields=["quantidade_disponivel"])
            return super().delete(*args, **kwargs)
