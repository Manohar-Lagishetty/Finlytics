def build_category_tree(categories):
    """Turn a flat list of a user's Category rows into a nested tree.

    Returns a list of {"category": Category, "children": [...]} nodes for
    root categories, each recursively holding its own children. Every node
    is visited exactly once (no query re-fetching) and ordering is by name
    at each level.
    """
    by_parent = {}
    for category in categories:
        by_parent.setdefault(category.parent_id, []).append(category)
    for siblings in by_parent.values():
        siblings.sort(key=lambda c: c.name.lower())

    def build(parent_id):
        return [
            {"category": category, "children": build(category.id)}
            for category in by_parent.get(parent_id, [])
        ]

    return build(None)


def flatten_tree(tree, depth=0):
    """Depth-first flatten of build_category_tree()'s output into
    (category, depth) pairs, preserving tree order."""
    for node in tree:
        yield node["category"], depth
        yield from flatten_tree(node["children"], depth + 1)


def descendant_ids(category):
    """All descendant category ids (children, grandchildren, ...) of a
    single category, via its `children` related manager. Used so filtering
    an expense list by a category also includes its subcategories."""
    ids = []
    frontier = list(category.children.all())
    while frontier:
        node = frontier.pop()
        ids.append(node.id)
        frontier.extend(node.children.all())
    return ids


def category_path_ids(category):
    """Root-to-leaf list of category ids for `category`, e.g. Food >
    Groceries > Snacks -> [Food.id, Groceries.id, Snacks.id]. Used to
    prefill the cascading category picker with an existing selection."""
    path = []
    node = category
    while node is not None:
        path.append(node.id)
        node = node.parent
    return list(reversed(path))


def root_category_id(category_id, categories_by_id):
    """Walk parent_id (a plain loaded field, no extra query) up to the
    root category id, given a {id: Category} map of a user's categories."""
    seen, current = set(), category_id
    while True:
        category = categories_by_id.get(current)
        if category is None or category.parent_id is None or current in seen:
            return current
        seen.add(current)
        current = category.parent_id


def nearest_budgeted_category_id(category, budgeted_category_ids):
    """Walk up from `category` (inclusive) via real .parent FK access,
    returning the nearest ancestor id present in budgeted_category_ids, or
    None. Used for the inline budget-status lookup on a single category,
    where a handful of extra queries for one interactive request is fine."""
    seen, current = set(), category
    while current is not None and current.id not in seen:
        if current.id in budgeted_category_ids:
            return current.id
        seen.add(current.id)
        current = current.parent
    return None


def group_amounts_by_root(rows, categories_by_id):
    """rows: iterable of (category_id, amount). Returns {root_id: total},
    summing every category's amount into its root category's bucket."""
    from collections import defaultdict
    from decimal import Decimal

    totals = defaultdict(lambda: Decimal("0"))
    for category_id, amount in rows:
        totals[root_category_id(category_id, categories_by_id)] += amount
    return totals


def add_months(d, months):
    """`d` shifted by `months`, clamped to the last valid day of the target
    month (e.g. Jan 31 + 1 month -> Feb 28/29, not an invalid Feb 31)."""
    import calendar

    month_index = d.month - 1 + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return d.replace(year=year, month=month, day=day)


def add_interval(d, interval):
    """Advance date `d` by one occurrence of a RecurringIncome.interval."""
    from datetime import timedelta

    if interval == "weekly":
        return d + timedelta(days=7)
    if interval == "biweekly":
        return d + timedelta(days=14)
    if interval == "monthly":
        return add_months(d, 1)
    if interval == "yearly":
        return add_months(d, 12)
    raise ValueError(f"Unknown recurring-income interval: {interval!r}")
