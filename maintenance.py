#!/usr/bin/env python3
"""Consistent, private backups of immutable videos and a SQLite snapshot."""
import argparse
import json
import os
import re
import sqlite3
import tarfile
import tempfile
import time
from pathlib import Path
import server

def backup(destination):
    destination=Path(destination).resolve()
    source=server.DATA/'academy.sqlite'
    if not source.is_file(): raise ValueError('No existe una base de datos para respaldar.')
    if destination.exists(): raise FileExistsError('El destino ya existe. Elige otro nombre.')
    destination.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='academy-backup-') as tmp:
        snapshot=Path(tmp)/'academy.sqlite'
        original=sqlite3.connect(source.resolve().as_uri()+'?mode=ro',uri=True,timeout=30)
        copy=sqlite3.connect(snapshot)
        try:
            original.backup(copy)
            # Restoring a backup must require a new sign-in. Incomplete uploads
            # are not referenced by lessons and must not be presented as recoverable.
            copy.execute('DELETE FROM sessions')
            copy.execute('DELETE FROM media WHERE ready=0')
            copy.commit()
            media=[row[0] for row in copy.execute('SELECT id FROM media WHERE ready=1')]
            if copy.execute('PRAGMA integrity_check').fetchone()[0]!='ok': raise ValueError('La base de datos no superó la verificación de integridad.')
        finally:
            original.close();copy.close()
        for mid in media:
            if not re.fullmatch('[a-f0-9]{32}',mid) or not (server.DATA/'media'/mid).is_file():
                raise ValueError('Falta un archivo de video. No se ha creado una copia incompleta.')
        manifest=Path(tmp)/'backup-info.json'
        manifest.write_text(json.dumps({'format':1,'created_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'videos':len(media),'sessions_restored':False},indent=2))
        fd,temporary=tempfile.mkstemp(prefix='.'+destination.name+'-',suffix='.incomplete',dir=destination.parent)
        try:
            with os.fdopen(fd,'wb') as output:
                with tarfile.open(fileobj=output,mode='w') as archive:
                    archive.add(snapshot,arcname='academy.sqlite')
                    archive.add(manifest,arcname='backup-info.json')
                    for mid in media: archive.add(server.DATA/'media'/mid,arcname='media/'+mid)
                output.flush();os.fsync(output.fileno())
            # Same-directory hard link publishes the completed archive without
            # replacing an existing backup, even if another process created it.
            os.link(temporary,destination)
        finally: Path(temporary).unlink(missing_ok=True)
    return len(media)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description='Copia consistente de Aumentados Academy; no modifica los datos originales.')
    parser.add_argument('command',choices=['backup']);parser.add_argument('destination',help='Nuevo archivo .tar privado')
    args=parser.parse_args()
    try:
        count=backup(args.destination)
        print(f'Copia verificada creada: {args.destination} ({count} videos). Guárdala en un lugar privado.')
    except (OSError,ValueError,sqlite3.Error) as e: parser.exit(1,f'No se pudo crear la copia: {e}\n')
