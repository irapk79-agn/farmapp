from django.db import models

DURATION_CHOICES = [
     ('', '— Select duration —'),
     ('25-40 days (~1 month)', '25–40 days (~1 month)'),
     ('2 months', '2 months'),
     ('3 months', '3 months'),
     ('4 months', '4 months'),
     ('5 months', '5 months'),
     ('6 months', '6 months'),
     ('9 months', '9 months'),
     ('12 months', '12 months'),
     ('perennial', 'Perennial'),
    ]

class Owner(models.Model):
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)

    def __str__(self):
        return self.name


class Block(models.Model):
    block_number = models.PositiveIntegerField(unique=True)
    owner = models.ForeignKey(Owner, on_delete=models.SET_NULL,
                              null=True, blank=True, related_name='blocks')
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"Block {self.block_number}"


class Row(models.Model):
    STATUS_CHOICES = [
        ('PLOWING', 'Plowing'),
        ('SEEDING', 'Seeding'),
        ('WATERING', 'Watering'),
        ('READY_TO_HARVEST', 'Ready to Harvest'),
        ('HARVESTED', 'Harvested'),
    ]
    count_per_plantation = models.CharField(
        max_length=50, blank=True,
        help_text="e.g. 100 plants, 101 rows"
    )
    yield_per_plantation = models.CharField(
        max_length=50, blank=True,
        help_text="e.g. 300 kg, 202 bunches"
    )
    rate = models.DecimalField(
        max_digits=10, decimal_places=2,
        null=True, blank=True,
        help_text="Rate per unit (e.g. 20 for ₹20/kg)"
    )
    duration = models.CharField(
        max_length=30, choices=DURATION_CHOICES, blank=True
    )
    
    @property
    def numeric_yield(self):
        """Extract the first number from yield_per_plantation (e.g. '300 kg' -> 300)."""
        import re
        if not self.yield_per_plantation:
            return None
        match = re.search(r'(\d+(?:\.\d+)?)', str(self.yield_per_plantation))
        return float(match.group(1)) if match else None

    @property
    def revenue_per_plantation(self):
        """Rate × Yield — returns None if either is missing."""
        if self.rate is None or self.numeric_yield is None:
            return None
        return float(self.rate) * self.numeric_yield

    @property
    def revenue_display(self):
        """Formatted revenue string for templates."""
        r = self.revenue_per_plantation
        if r is None:
            return '—'
        return f"₹{r:,.2f}" 
    PLANT_ICONS = {
        'mango': '🥭',
        'coconut': '🌴',
        'coconut tree': '🌴',
        'banana': '🍌',
        'tomato': '🍅',
        'potato': '🥔',
        'onion': '🧅',
        'carrot': '🥕',
        'corn': '🌽',
        'maize': '🌽',
        'rice': '🌾',
        'paddy': '🌾',
        'wheat': '🌾',
        'sugarcane': '🎋',
        'tea': '🍃',
        'coffee': '☕',
        'grape': '🍇',
        'grapes': '🍇',
        'apple': '🍎',
        'orange': '🍊',
        'lemon': '🍋',
        'watermelon': '🍉',
        'strawberry': '🍓',
        'pepper': '🌶️',
        'chilli': '🌶️',
        'chili': '🌶️',
        'brinjal': '🍆',
        'eggplant': '🍆',
        'cucumber': '🥒',
        'pumpkin': '🎃',
        'groundnut': '🥜',
        'peanut': '🥜',
        'sunflower': '🌻',
        'rose': '🌹',
        'flower': '🌸',
        'tulsi': '🌿',
        'herb': '🌿',
    }

    
    @property
    def plant_icon(self):
        if not self.plant_type:
            return '🌱'   # default seedling
        key = self.plant_type.strip().lower()
        # Try exact match first
        if key in self.PLANT_ICONS:
            return self.PLANT_ICONS[key]
        # Then try substring match (e.g. "mango tree" → mango)
        for name, icon in self.PLANT_ICONS.items():
            if name in key:
                return icon
        return '🌱' 

    block = models.ForeignKey(Block, on_delete=models.CASCADE, related_name='rows')
    row_number = models.PositiveIntegerField()
    plant_type = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PLOWING')
    planted_date = models.DateField(null=True, blank=True)
    harvest_date = models.DateField(null=True, blank=True)

    class Meta:
        unique_together = ('block', 'row_number')
        ordering = ['block__block_number', 'row_number']

    def __str__(self):
        return f"B{self.block.block_number}-R{self.row_number} ({self.status})"