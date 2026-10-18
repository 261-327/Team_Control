"""Validation shared by the JSON API and archived Django pages."""

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.db.models.functions import Lower, Trim
from .models import Membership, WorkspaceUser


class WorkspaceUserCreationForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        label="Электронная почта",
        error_messages={
            "required": "Укажите почту, на которую отправить код.",
            "invalid": "Введите корректный адрес почты, например name@example.com.",
        },
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Логин"
        self.fields["first_name"].label = "Имя"
        self.fields["last_name"].label = "Фамилия"
        self.fields["password1"].label = "Пароль"
        self.fields["password2"].label = "Повторите пароль"
        for field in self.fields.values():
            field.error_messages["required"] = "Заполните это поле."
        self.fields["email"].error_messages["required"] = "Укажите почту, на которую отправить код."
        self.fields["username"].error_messages.update(
            {
                "unique": "Этот логин уже занят. Выберите другой или войдите в существующий аккаунт.",
                "invalid": "Логин может содержать только буквы, цифры и символы @ . + - _.",
            }
        )
        self.error_messages = {
            **self.error_messages,
            "password_mismatch": "Пароли не совпадают. Введите одинаковый пароль в обоих полях.",
        }

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if (
            WorkspaceUser.objects.annotate(normalized_email=Lower(Trim("email")))
            .filter(normalized_email=email)
            .exists()
        ):
            raise forms.ValidationError(
                "Эта почта уже зарегистрирована. Войдите в существующий аккаунт или укажите другую почту."
            )
        return email

    class Meta(UserCreationForm.Meta):
        model = WorkspaceUser
        fields = UserCreationForm.Meta.fields + ("email", "first_name", "last_name")


class MembershipRoleForm(forms.ModelForm):
    class Meta:
        model = Membership
        fields = ("role", "developer_specialization", "custom_role")
        labels = {"role": "Ваша роль в проекте", "custom_role": "Своя роль в проекте"}
