from django.core.management.base import BaseCommand
from farm.models import Block, Row


class Command(BaseCommand):
    help = "Initialize 100 blocks with 20 rows each"

    def handle(self, *args, **kwargs):
        for b_num in range(1, 101):
            block, _ = Block.objects.get_or_create(block_number=b_num)
            for r_num in range(1, 21):
                Row.objects.get_or_create(block=block, row_number=r_num)
        self.stdout.write(self.style.SUCCESS(
            "Land initialized: 100 blocks x 20 rows = 2000 rows"
        ))