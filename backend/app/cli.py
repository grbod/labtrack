"""Command-line interface for LabTrack."""

import click
import asyncio
from pathlib import Path
from datetime import datetime, date
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import pandas as pd

# Load environment variables
load_dotenv()

from .config import settings
from .database import Base, SessionLocal
from .models import Product, Lot, LotType, LotStatus, UserRole
from .services import (
    ProductService,
    LotService,
    UserService,
    PDFParserService,
    PDFWatcherService,
    COAGeneratorService,
)
from .utils.logger import logger


@click.group()
def cli():
    """LabTrack CLI."""
    pass


# Database commands
@cli.group()
def db():
    """Database management commands."""
    pass


@db.command()
def init():
    """Initialize the database."""
    click.echo("Initializing database...")
    try:
        engine = create_engine(settings.DATABASE_URL)
        Base.metadata.create_all(engine)
        click.echo("✅ Database initialized successfully!")
    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)


@db.command()
@click.confirmation_option(prompt="Are you sure you want to drop all tables?")
def reset():
    """Reset the database (drop and recreate all tables)."""
    click.echo("Resetting database...")
    try:
        engine = create_engine(settings.DATABASE_URL)
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        click.echo("✅ Database reset successfully!")
    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)


# Product commands
@cli.group()
def product():
    """Product management commands."""
    pass


@product.command()
@click.option("--brand", prompt=True, help="Product brand")
@click.option("--name", prompt=True, help="Product name")
@click.option("--flavor", help="Product flavor")
@click.option("--size", help="Product size")
@click.option("--display-name", help="Display name for COAs")
def add(brand, name, flavor, size, display_name):
    """Add a new product."""
    db = SessionLocal()
    try:
        service = ProductService(db)

        # Auto-generate display name if not provided
        if not display_name:
            display_name = f"{brand} {name}"
            if flavor:
                display_name += f" - {flavor}"
            if size:
                display_name += f" ({size})"

        product = service.create(
            brand=brand,
            product_name=name,
            flavor=flavor,
            size=size,
            display_name=display_name,
        )

        click.echo(f"✅ Product added: {product.display_name} (ID: {product.id})")

    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
    finally:
        db.close()


@product.command()
@click.option("--limit", default=20, help="Number of products to show")
def list(limit):
    """List all products."""
    db = SessionLocal()
    try:
        service = ProductService(db)
        products = service.get_all()[:limit]

        if products:
            click.echo(f"\nFound {len(products)} products:\n")
            for p in products:
                click.echo(f"ID: {p.id} | {p.display_name}")
                click.echo(f"   Brand: {p.brand} | Product: {p.product_name}")
                if p.flavor or p.size:
                    click.echo(
                        f"   Flavor: {p.flavor or 'N/A'} | Size: {p.size or 'N/A'}"
                    )
                click.echo()
        else:
            click.echo("No products found.")

    finally:
        db.close()


# Sample commands
@cli.group()
def sample():
    """Sample management commands."""
    pass


@sample.command()
@click.option("--product-id", type=int, prompt=True, help="Product ID")
@click.option("--lot-number", prompt=True, help="Lot number")
@click.option(
    "--type", type=click.Choice(["standard", "parent_lot"]), default="standard"
)
@click.option(
    "--mfg-date", type=click.DateTime(formats=["%Y-%m-%d"]), default=str(date.today())
)
@click.option("--exp-date", type=click.DateTime(formats=["%Y-%m-%d"]), prompt=True)
def create(product_id, lot_number, type, mfg_date, exp_date):
    """Create a new sample."""
    db = SessionLocal()
    try:
        service = LotService(db)

        lot = service.create_lot(
            lot_number=lot_number,
            lot_type=LotType(type),
            product_ids=[product_id],
            mfg_date=mfg_date.date(),
            exp_date=exp_date.date(),
        )

        click.echo(f"✅ Sample created successfully!")
        click.echo(f"   Reference Number: {lot.reference_number}")
        click.echo(f"   Lot Number: {lot.lot_number}")
        click.echo(f"   Type: {lot.lot_type.value}")

    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
    finally:
        db.close()


@sample.command("create-sublots")
@click.option("--parent", prompt="Parent lot number", help="Parent lot number")
@click.option("--count", type=int, prompt=True, help="Number of sublots")
@click.option("--quantity", type=float, help="Quantity per sublot (lbs)")
def create_sublots(parent, count, quantity):
    """Create sublots under a parent lot."""
    db = SessionLocal()
    try:
        service = LotService(db)

        # Find parent lot
        parent_lot = db.query(Lot).filter_by(lot_number=parent).first()
        if not parent_lot:
            click.echo(f"❌ Parent lot '{parent}' not found", err=True)
            return

        sublots = service.create_sublots(
            parent_lot_id=parent_lot.id, count=count, quantity_per_sublot=quantity
        )

        click.echo(f"✅ Created {len(sublots)} sublots:")
        for sublot in sublots:
            click.echo(f"   - {sublot.sublot_number}")

    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
    finally:
        db.close()


# PDF commands
@cli.group()
def pdf():
    """PDF processing commands."""
    pass


@pdf.command("parse")
@click.argument("pdf_path", type=click.Path(exists=True))
def parse_pdf(pdf_path):
    """Parse a PDF file."""
    db = SessionLocal()
    try:
        service = PDFParserService(db)

        click.echo(f"Parsing PDF: {pdf_path}")

        # Run async function
        result = asyncio.run(service.parse_pdf(Path(pdf_path)))

        if result["status"] == "success":
            click.echo("✅ PDF parsed successfully!")
            click.echo(f"   Confidence: {result['confidence']:.1%}")

            data = result["data"]
            click.echo(f"   Reference: {data.get('reference_number', 'N/A')}")
            click.echo(f"   Lot: {data.get('lot_number', 'N/A')}")

        elif result["status"] == "review_needed":
            click.echo("⚠️  PDF parsed but needs manual review")
            click.echo(f"   Queue ID: {result['queue_id']}")

        else:
            click.echo(
                f"❌ Failed to parse PDF: {result.get('error', 'Unknown error')}",
                err=True,
            )

    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
    finally:
        db.close()


@pdf.command("watch")
@click.option("--folder", type=click.Path(), help="Folder to watch")
def watch_folder(folder):
    """Start watching a folder for PDFs."""
    db = SessionLocal()
    try:
        if folder:
            service = PDFWatcherService(db, Path(folder))
        else:
            service = PDFWatcherService(db)

        click.echo(f"👁️  Watching folder: {service.watch_dir}")
        click.echo("Press Ctrl+C to stop...")

        service.start_watching()

        # Keep running until interrupted
        try:
            while True:
                asyncio.run(asyncio.sleep(1))
        except KeyboardInterrupt:
            click.echo("\nStopping watcher...")
            service.stop_watching()

    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
    finally:
        db.close()


# COA commands
@cli.group()
def coa():
    """COA generation commands."""
    pass


@coa.command("generate")
@click.option("--lot", prompt="Lot number", help="Lot number to generate COA for")
@click.option("--template", default="standard", help="Template to use")
@click.option("--format", type=click.Choice(["pdf", "docx", "both"]), default="pdf")
def generate_coa(lot, template, format):
    """Generate COA for a lot."""
    db = SessionLocal()
    try:
        # Find lot
        lot_obj = db.query(Lot).filter_by(lot_number=lot).first()
        if not lot_obj:
            click.echo(f"❌ Lot '{lot}' not found", err=True)
            return

        service = COAGeneratorService(db)
        result = service.generate_coa(
            lot_id=lot_obj.id, template=template, output_format=format
        )

        click.echo("✅ COA generated successfully!")
        for file in result["files"]:
            click.echo(f"   📄 {file}")

    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
    finally:
        db.close()


@coa.command("status")
@click.option("--pending", is_flag=True, help="Show only pending lots")
def coa_status(pending):
    """Show lots ready for COA generation."""
    db = SessionLocal()
    try:
        query = db.query(Lot).filter(Lot.generate_coa == True)

        if pending:
            query = query.filter(Lot.status == LotStatus.APPROVED)

        lots = query.all()

        if lots:
            click.echo(f"\nFound {len(lots)} lots:\n")
            for lot in lots:
                products = ", ".join(
                    [lp.product.display_name for lp in lot.lot_products]
                )
                click.echo(f"Lot: {lot.lot_number} | Ref: {lot.reference_number}")
                click.echo(f"   Status: {lot.status.value}")
                click.echo(f"   Product(s): {products}")
                click.echo()
        else:
            click.echo("No lots found.")

    finally:
        db.close()


# User commands
@cli.group()
def user():
    """User management commands."""
    pass


@user.command("create")
@click.option("--username", prompt=True)
@click.option("--email", prompt=True)
@click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True)
@click.option(
    "--role",
    type=click.Choice(["admin", "qc_manager", "lab_tech", "read_only"]),
    prompt=True,
)
def create_user(username, email, password, role):
    """Create a new user."""
    db = SessionLocal()
    try:
        service = UserService(db)

        user = service.create_user(
            username=username, email=email, password=password, role=UserRole(role)
        )

        click.echo(f"✅ User created: {user.username} ({user.role.value})")

    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
    finally:
        db.close()


# Report command
@cli.command()
@click.option(
    "--from", "from_date", type=click.DateTime(formats=["%Y-%m-%d"]), required=True
)
@click.option(
    "--to", "to_date", type=click.DateTime(formats=["%Y-%m-%d"]), required=True
)
@click.option("--output", type=click.Path(), help="Output file path")
def report(from_date, to_date, output):
    """Generate activity report."""
    db = SessionLocal()
    try:
        # Gather report data
        lots = (
            db.query(Lot)
            .filter(Lot.created_at >= from_date, Lot.created_at <= to_date)
            .all()
        )

        click.echo(f"\n📊 Activity Report: {from_date.date()} to {to_date.date()}\n")
        click.echo(f"Total Lots Created: {len(lots)}")

        # Status breakdown
        status_counts = {}
        for lot in lots:
            status = lot.status.value
            status_counts[status] = status_counts.get(status, 0) + 1

        click.echo("\nStatus Breakdown:")
        for status, count in status_counts.items():
            click.echo(f"   {status}: {count}")

        # TODO: Add more report details

        if output:
            click.echo(f"\n📄 Report saved to: {output}")

    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
    finally:
        db.close()


if __name__ == "__main__":
    cli()
