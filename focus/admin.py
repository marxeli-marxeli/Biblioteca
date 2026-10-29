from django.contrib import admin
from django.contrib import messages

from .models import Emprestimo, Leitor, Livro


@admin.register(Livro)
class LivroAdmin(admin.ModelAdmin):
    list_display = (
        "titulo",
        "autor",
        "isbn",
        "quantidade_disponivel",
        "quantidade_total",
    )
    search_fields = ("titulo", "autor", "isbn")


@admin.register(Leitor)
class LeitorAdmin(admin.ModelAdmin):
    list_display = ("nome", "email", "telefone", "cadastrado_em")
    search_fields = ("nome", "email")


@admin.register(Emprestimo)
class EmprestimoAdmin(admin.ModelAdmin):
    list_display = ("livro", "leitor", "data_emprestimo", "data_prevista", "status")
    list_filter = ("data_emprestimo", "devolvido_em")
    search_fields = ("livro__titulo", "leitor__nome", "leitor__email")
    readonly_fields = ("devolvido_em",)
    actions = ("marcar_como_devolvidos",)

    def get_readonly_fields(self, request, obj=None):
        # Depois de criado, o vínculo do registro não pode ser substituído no admin.
        if obj:
            return self.readonly_fields + ("livro", "leitor", "data_emprestimo")
        return self.readonly_fields

    @admin.display(description="situação")
    def status(self, obj):
        return "Devolvido" if obj.devolvido_em else "Em aberto"

    def delete_queryset(self, request, queryset):
        # A exclusão padrão em lote ignora o método delete() de cada empréstimo.
        for emprestimo in queryset.iterator():
            emprestimo.delete()

    @admin.action(description="Marcar empréstimos selecionados como devolvidos")
    def marcar_como_devolvidos(self, request, queryset):
        quantidade = 0
        for emprestimo in queryset:
            if emprestimo.marcar_como_devolvido():
                quantidade += 1
        self.message_user(
            request,
            f"{quantidade} empréstimo(s) marcado(s) como devolvido(s).",
            level=messages.SUCCESS,
        )
