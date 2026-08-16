from decimal import Decimal

from django import forms
from django.utils import timezone

from .models import Budget, Category, Expense, FinanceSettings, Income, RecurringIncome
from .utils import build_category_tree, flatten_tree

DATETIME_LOCAL_FORMAT = "%Y-%m-%dT%H:%M"

INPUT_CLASSES = (
    "w-full rounded-xl border border-slate-200 dark:border-slate-700 "
    "bg-white/70 dark:bg-slate-900/60 px-4 py-3 text-sm text-slate-900 dark:text-slate-100 "
    "placeholder:text-slate-400 dark:placeholder:text-slate-500 outline-none transition "
    "focus:border-brand-500 focus:ring-4 focus:ring-brand-500/15"
)


class ExpenseForm(forms.ModelForm):
    date = forms.DateTimeField(
        input_formats=[DATETIME_LOCAL_FORMAT],
        widget=forms.DateTimeInput(format=DATETIME_LOCAL_FORMAT, attrs={"class": INPUT_CLASSES, "type": "datetime-local"}),
    )

    class Meta:
        model = Expense
        fields = ["amount", "category", "date", "location", "payment_type", "payment_source", "note"]
        widgets = {
            "amount": forms.NumberInput(
                attrs={
                    "class": INPUT_CLASSES, "step": "0.01", "min": "0.01", "placeholder": "0.00", "inputmode": "decimal",
                    "x-model.number": "amountValue",
                }
            ),
            "location": forms.TextInput(attrs={"class": INPUT_CLASSES, "placeholder": "e.g. Downtown Mall", "maxlength": 255}),
            "payment_type": forms.Select(attrs={"class": INPUT_CLASSES}),
            "payment_source": forms.TextInput(attrs={"class": INPUT_CLASSES, "placeholder": "e.g. HDFC Bank (optional)", "maxlength": 100}),
            "note": forms.TextInput(attrs={"class": INPUT_CLASSES, "placeholder": "Optional note", "maxlength": 255}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields["date"].initial = timezone.localtime()
        self.fields["category"].queryset = Category.objects.filter(user=user)
        # Selection happens through the JS-driven cascading picker; this
        # field just carries the chosen category id to the server.
        self.fields["category"].widget = forms.HiddenInput()

    def clean_category(self):
        category = self.cleaned_data.get("category")
        if category is None or category.user_id != self.user.id:
            raise forms.ValidationError("Choose a valid category.")
        return category


def _category_label(category):
    depth = getattr(category, "_choice_depth", 0)
    return f"{'— ' * depth}{category.name}"


def tree_choices(user, empty_label):
    """(value, label) choice pairs for a user's categories in tree order
    (parent immediately followed by its children), indented by depth."""
    categories = list(Category.objects.filter(user=user))
    ordered = list(flatten_tree(build_category_tree(categories)))
    for category, depth in ordered:
        category._choice_depth = depth
    return [("", empty_label)] + [(category.pk, _category_label(category)) for category, _ in ordered]


class CategoryLabelChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, category):
        return _category_label(category)


class CategoryForm(forms.ModelForm):
    parent = CategoryLabelChoiceField(
        queryset=Category.objects.none(),
        required=False,
        label="Parent category",
        empty_label="None (top-level category)",
        widget=forms.Select(attrs={"class": INPUT_CLASSES}),
    )

    class Meta:
        model = Category
        fields = ["name", "parent"]
        widgets = {
            "name": forms.TextInput(attrs={"class": INPUT_CLASSES, "placeholder": "e.g. Groceries", "maxlength": 80}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        parent_field = self.fields["parent"]
        parent_field.queryset = Category.objects.filter(user=user)
        # Render options in tree order (parent immediately followed by its
        # children) instead of the queryset's default alphabetical order,
        # so the indentation added by CategoryLabelChoiceField reads right.
        parent_field.choices = tree_choices(user, parent_field.empty_label)

    def clean_name(self):
        return self.cleaned_data["name"].strip()

    def clean(self):
        cleaned_data = super().clean()
        name = cleaned_data.get("name")
        parent = cleaned_data.get("parent")
        if name and Category.objects.filter(user=self.user, parent=parent, name__iexact=name).exists():
            self.add_error("name", "You already have a category with this name at this level.")
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.user = self.user
        if commit:
            instance.save()
        return instance


FILTER_INPUT_CLASSES = INPUT_CLASSES.replace("px-4 py-3", "px-3.5 py-2.5")


class ExpenseFilterForm(forms.Form):
    date_from = forms.DateField(
        required=False, widget=forms.DateInput(attrs={"class": FILTER_INPUT_CLASSES, "type": "date"})
    )
    date_to = forms.DateField(
        required=False, widget=forms.DateInput(attrs={"class": FILTER_INPUT_CLASSES, "type": "date"})
    )
    category = CategoryLabelChoiceField(
        queryset=Category.objects.none(),
        required=False,
        empty_label="All categories",
        widget=forms.Select(attrs={"class": FILTER_INPUT_CLASSES}),
    )
    amount_min = forms.DecimalField(
        required=False, min_value=Decimal("0"),
        widget=forms.NumberInput(attrs={"class": FILTER_INPUT_CLASSES, "step": "0.01", "placeholder": "Min"}),
    )
    amount_max = forms.DecimalField(
        required=False, min_value=Decimal("0"),
        widget=forms.NumberInput(attrs={"class": FILTER_INPUT_CLASSES, "step": "0.01", "placeholder": "Max"}),
    )
    q = forms.CharField(
        required=False, max_length=255,
        widget=forms.TextInput(attrs={"class": FILTER_INPUT_CLASSES, "placeholder": "Search notes…"}),
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        category_field = self.fields["category"]
        category_field.queryset = Category.objects.filter(user=user)
        category_field.choices = tree_choices(user, category_field.empty_label)

    def clean(self):
        cleaned_data = super().clean()
        date_from, date_to = cleaned_data.get("date_from"), cleaned_data.get("date_to")
        if date_from and date_to and date_from > date_to:
            self.add_error("date_to", "End date must be on or after the start date.")
        amount_min, amount_max = cleaned_data.get("amount_min"), cleaned_data.get("amount_max")
        if amount_min is not None and amount_max is not None and amount_min > amount_max:
            self.add_error("amount_max", "Max must be at least the min amount.")
        return cleaned_data


class IncomeForm(forms.ModelForm):
    date = forms.DateTimeField(
        input_formats=[DATETIME_LOCAL_FORMAT],
        widget=forms.DateTimeInput(format=DATETIME_LOCAL_FORMAT, attrs={"class": INPUT_CLASSES, "type": "datetime-local"}),
    )

    class Meta:
        model = Income
        fields = ["amount", "date", "source", "note"]
        widgets = {
            "amount": forms.NumberInput(
                attrs={"class": INPUT_CLASSES, "step": "0.01", "min": "0.01", "placeholder": "0.00", "inputmode": "decimal"}
            ),
            "source": forms.TextInput(attrs={"class": INPUT_CLASSES, "placeholder": "e.g. Freelance, Gift, Refund", "maxlength": 100}),
            "note": forms.TextInput(attrs={"class": INPUT_CLASSES, "placeholder": "Optional note", "maxlength": 255}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields["date"].initial = timezone.localtime()

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.user = self.user
        if commit:
            instance.save()
        return instance


class RecurringIncomeForm(forms.ModelForm):
    start_date = forms.DateField(
        widget=forms.DateInput(attrs={"class": INPUT_CLASSES, "type": "date"}),
        help_text="The first credit date. Later credits repeat on this same day (monthly/yearly) or weekday (weekly/biweekly).",
    )

    class Meta:
        model = RecurringIncome
        fields = ["label", "amount", "interval", "start_date"]
        widgets = {
            "label": forms.TextInput(attrs={"class": INPUT_CLASSES, "placeholder": "e.g. Salary", "maxlength": 100}),
            "amount": forms.NumberInput(
                attrs={"class": INPUT_CLASSES, "step": "0.01", "min": "0.01", "placeholder": "0.00", "inputmode": "decimal"}
            ),
            "interval": forms.Select(attrs={"class": INPUT_CLASSES}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.user = self.user
        instance.next_due_date = instance.start_date
        if commit:
            instance.save()
        return instance


class IncomeFilterForm(forms.Form):
    date_from = forms.DateField(
        required=False, widget=forms.DateInput(attrs={"class": FILTER_INPUT_CLASSES, "type": "date"})
    )
    date_to = forms.DateField(
        required=False, widget=forms.DateInput(attrs={"class": FILTER_INPUT_CLASSES, "type": "date"})
    )
    q = forms.CharField(
        required=False, max_length=255,
        widget=forms.TextInput(attrs={"class": FILTER_INPUT_CLASSES, "placeholder": "Search source or notes…"}),
    )

    def clean(self):
        cleaned_data = super().clean()
        date_from, date_to = cleaned_data.get("date_from"), cleaned_data.get("date_to")
        if date_from and date_to and date_from > date_to:
            self.add_error("date_to", "End date must be on or after the start date.")
        return cleaned_data


class BudgetForm(forms.ModelForm):
    category = CategoryLabelChoiceField(
        queryset=Category.objects.none(),
        widget=forms.Select(attrs={"class": INPUT_CLASSES}),
    )

    class Meta:
        model = Budget
        fields = ["category", "monthly_cap"]
        widgets = {
            "monthly_cap": forms.NumberInput(
                attrs={"class": INPUT_CLASSES, "step": "0.01", "min": "0.01", "placeholder": "0.00", "inputmode": "decimal"}
            ),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        category_field = self.fields["category"]
        category_field.queryset = Category.objects.filter(user=user)
        # Drop the leading blank entry tree_choices() adds for optional
        # fields - a budget must target a real category.
        category_field.choices = tree_choices(user, "")[1:]

    def clean_category(self):
        category = self.cleaned_data.get("category")
        if category is not None and Budget.objects.filter(user=self.user, category=category).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("This category already has a budget. Edit it instead of creating a new one.")
        return category

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.user = self.user
        if commit:
            instance.save()
        return instance


class FinanceSettingsForm(forms.ModelForm):
    class Meta:
        model = FinanceSettings
        fields = ["low_balance_threshold"]
        widgets = {
            "low_balance_threshold": forms.NumberInput(
                attrs={"class": INPUT_CLASSES, "step": "0.01", "min": "0", "placeholder": "0.00", "inputmode": "decimal"}
            ),
        }
