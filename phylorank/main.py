###############################################################################
#                                                                             #
#    This program is free software: you can redistribute it and/or modify     #
#    it under the terms of the GNU General Public License as published by     #
#    the Free Software Foundation, either version 3 of the License, or        #
#    (at your option) any later version.                                      #
#                                                                             #
#    This program is distributed in the hope that it will be useful,          #
#    but WITHOUT ANY WARRANTY; without even the implied warranty of           #
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the            #
#    GNU General Public License for more details.                             #
#                                                                             #
#    You should have received a copy of the GNU General Public License        #
#    along with this program. If not, see <http://www.gnu.org/licenses/>.     #
#                                                                             #
###############################################################################

import os
import sys
import logging
from collections import defaultdict

from phylorank.decorate_tree import DecorateTree
from phylorank.rel_dist import RelativeDistance
from phylorank.newick import parse_label
from phylorank.outliers import Outliers
from phylorank.rd_ranks import RdRanks
from phylorank.bl_dist import BranchLengthDistribution
from phylorank.tree_diff import TreeDiff
from phylorank.plot.robustness_plot import RobustnessPlot
from phylorank.plot.distribution_plot import DistributionPlot

from biolib.common import (make_sure_path_exists,
                           check_dir_exists,
                           check_file_exists)
from biolib.taxonomy import Taxonomy
from biolib.misc.time_keeper import TimeKeeper
from biolib.external.execute import check_dependencies

from numpy import (mean as np_mean)

import dendropy

class OptionsParser():
    def __init__(self):
        """Initialization"""
        self.logger = logging.getLogger()
        self.time_keeper = TimeKeeper()

    def outliers(self, options):
        """Create information for identifying taxnomic outliers"""

        check_file_exists(options.input_tree)

        if options.plot_taxa_file:
            check_file_exists(options.plot_taxa_file)

        if options.trusted_taxa_file:
            check_file_exists(options.trusted_taxa_file)

        if not os.path.exists(options.output_dir):
            os.makedirs(options.output_dir)

        o = Outliers(options.dpi)
        o.run(options.input_tree,
                options.taxonomy_file,
                options.output_dir,
                options.plot_taxa_file,
                options.plot_dist_taxa_only,
                options.plot_domain,
                options.trusted_taxa_file,
                options.fixed_root,
                options.min_children,
                options.min_support,
                options.verbose_table)

        self.logger.info('Done.')
        
    def scale(self, options):
        """Scale command"""

        check_file_exists(options.input_tree)
        
        if not os.path.exists(options.output_dir):
            os.makedirs(options.output_dir)
        
        outliers = Outliers()
        outliers.scale(options.input_tree,
                        options.taxonomy_file,
                        options.output_dir,
                        options.trusted_taxa_file,
                        options.fixed_root,
                        options.min_children,
                        options.min_support)
        
        self.logger.info('Done.')
        
    def tree_diff(self, options):
        """Tree diff command."""
        
        check_file_exists(options.input_tree1)
        check_file_exists(options.input_tree2)
        
        td = TreeDiff()
        td.run(options.input_tree1,
                options.input_tree2,
                options.output_file,
                options.min_support,
                options.min_taxa,
                options.named_only)
        
        self.logger.info('Done.')
        
    def dist_plot(self, options):
        """Distribution plot command"""

        check_file_exists(options.input_tree)

        if options.plot_taxa_file:
            check_file_exists(options.plot_taxa_file)

        if options.trusted_taxa_file:
            check_file_exists(options.trusted_taxa_file)

        dist_plot = DistributionPlot()
        dist_plot.run(options.input_tree,
                            options.output_prefix,
                            options.plot_taxa_file,
                            options.trusted_taxa_file,
                            options.min_children,
                            options.min_support)

        self.logger.info('Done.')

    def decorate(self, options):
        """Decorate command"""

        check_file_exists(options.input_tree)

        dt = DecorateTree()
        dt.run(options.input_tree,
                    options.output_tree,
                    options.min_support,
                    options.only_named_clades,
                    options.min_length,
                    not options.no_percentile,
                    not options.no_relative_divergence,
                    not options.no_prediction,
                    options.thresholds)

        self.logger.info('Decorated tree written to: %s' % options.output_tree)
   
    def pull(self, options):
        """Pull command"""
        check_file_exists(options.input_tree)

        t = Taxonomy().read_from_tree(options.input_tree) #, False)
        if not options.no_rank_fill:
            for taxon_id, taxa in t.iteritems():
                t[taxon_id] = Taxonomy().fill_missing_ranks(taxa)

        Taxonomy().write(t, options.output_file)

        self.logger.info('Taxonomy strings written to: %s' % options.output_file)

    def validate(self, options):
        """Validate command"""

        check_file_exists(options.taxonomy_file)

        taxonomy = Taxonomy()
        t = taxonomy.read(options.taxonomy_file)

        errors = taxonomy.validate(t,
                                     not options.no_prefix,
                                     not options.no_all_ranks,
                                     not options.no_hierarhcy,
                                     not options.no_species,
                                     True)

        invalid_ranks, invalid_prefixes, invalid_species_name, invalid_hierarchies = errors

        if sum([len(e) for e in errors]) == 0:
            self.logger.info('No errors identified in taxonomy file.')
        else:
            self.logger.info('Identified %d incomplete taxonomy strings.' % len(invalid_ranks))
            self.logger.info('Identified %d rank prefix errors.' % len(invalid_prefixes))
            self.logger.info('Identified %d invalid species names.' % len(invalid_species_name))
            self.logger.info('Identified %d taxa with multiple parents.' % len(invalid_hierarchies))

    def append(self, options):
        """Append command"""
        self.logger.info('')
        self.logger.info('*******************************************************************************')
        self.logger.info(' [PhyloRank - append] Appending taxonomy to extant tree labels.')
        self.logger.info('*******************************************************************************')

        check_file_exists(options.input_tree)
        check_file_exists(options.taxonomy_file)

        taxonomy = Taxonomy().read(options.taxonomy_file)

        tree = dendropy.Tree.get_from_path(options.input_tree, 
                                            schema='newick', 
                                            rooting='force-rooted', 
                                            preserve_underscores=True)
        
        for n in tree.leaf_node_iter():
            taxa_str = taxonomy.get(n.label, None)
            if taxa_str == None:
                self.logger.error('Taxonomy file does not contain an entry for %s.' % n.label)
                sys.exit(-1)
            n.label = n.label + '|' + ';'.join(taxonomy[n.label])

        tree.write_to_path(options.output_tree, 
                            schema='newick', 
                            suppress_rooting=True, 
                            unquoted_underscores=True)

        self.logger.info('')
        self.logger.info('  Decorated tree written to: %s' % options.output_tree)

        self.time_keeper.print_time_stamp()

    def taxon_stats(self, options):
        """Taxon stats command"""
        check_file_exists(options.taxonomy_file)

        taxonomy = Taxonomy().read(options.taxonomy_file)
        taxon_children = Taxonomy().taxon_children(taxonomy)

        fout = open(options.output_file, 'w')
        fout.write('Taxa')
        for rank in Taxonomy.rank_labels[1:]:
            fout.write('\t# named %s' % rank)
        fout.write('\t# extant taxon with complete taxonomy')
        fout.write('\n')

        for rank_prefix in Taxonomy.rank_prefixes:
            # find taxon at the specified rank
            cur_taxa = []
            for taxon in taxon_children:
                if taxon.startswith(rank_prefix):
                    cur_taxa.append(taxon)

            cur_taxa.sort()

            for taxon in cur_taxa:
                fout.write(taxon)
                fout.write('\t-' * Taxonomy.rank_index[rank_prefix])

                next_taxa = [taxon]
                for _ in xrange(Taxonomy.rank_index[rank_prefix], Taxonomy.rank_index['s__'] + 1):
                    children_taxa = set()
                    for t in next_taxa:
                        children_taxa.update(taxon_children[t])

                    fout.write('\t%d' % len(children_taxa))
                    next_taxa = children_taxa
                fout.write('\n')

        fout.close()

        self.logger.info('Summary statistics written to: %s' % options.output_file)

    def robustness_plot(self, options):
        """Robustness plot command"""
        self.logger.info('')
        self.logger.info('*******************************************************************************')
        self.logger.info(' [PhyloRank - robustness_plot] Plotting distances across a set of tree.')
        self.logger.info('*******************************************************************************')

        robustness_plot = RobustnessPlot()
        robustness_plot.run(options.rank,
                                options.input_tree_dir,
                                options.full_tree_file,
                                options.derep_tree_file,
                                options.taxonomy_file,
                                options.output_prefix,
                                options.min_children,
                                options.title)

        self.time_keeper.print_time_stamp()

    def rd_ranks(self, options):
        """Calculate number of taxa for specified rd thresholds."""

        check_file_exists(options.input_tree)
        make_sure_path_exists(options.output_dir)

        r = RdRanks()
        r.run(options.input_tree,
                options.thresholds,
                options.output_dir)

        self.logger.info('Done.')
        
    def bl_dist(self, options):
        """Calculate distribution of branch lengths at each taxonomic rank."""

        check_file_exists(options.input_tree)
        make_sure_path_exists(options.output_dir)

        b = BranchLengthDistribution()
        b.run(options.input_tree,
                options.trusted_taxa_file,
                options.min_children,
                options.taxonomy_file,
                options.output_dir)

        self.logger.info('Done.')
        
    def bl_optimal(self, options):
        """Determine branch length for best congruency with existing taxonomy."""
        
        b = BranchLengthDistribution()
        optimal_bl, correct_taxa, incorrect_taxa = b.optimal(options.input_tree, 
                                                                options.rank,
                                                                options.output_table)
        
        prec = float(correct_taxa) / (correct_taxa + incorrect_taxa)
        
        self.logger.info('Optimal branch length is %f.' % optimal_bl)
        self.logger.info('This results in %d correct and %d incorrect taxa (precision = %.2f).' % (correct_taxa, incorrect_taxa, prec))
        
    def bl_decorate(self, options):
        """Decorate tree based using a mean branch length criterion."""
        
        check_file_exists(options.input_tree)
        
        b = BranchLengthDistribution()
        b.decorate(options.input_tree, 
                    options.taxonomy_file,
                    options.threshold, 
                    options.rank, 
                    options.retain_named_lineages,
                    options.keep_labels,
                    options.prune,
                    options.output_tree)
        
        self.logger.info('Done.')
        
    def bl_table(self, options):
        """Produce table with number of lineage for increasing mean branch lengths."""

        check_file_exists(options.input_tree)
        check_file_exists(options.taxon_category)

        b = BranchLengthDistribution()
        b.table(options.input_tree,
                options.taxon_category,
                options.step_size,
                options.output_table)

        self.logger.info('Done.')
        
    def rank_res(self, options):
        """Calculate taxonomic resolution at each rank."""

        check_file_exists(options.input_tree)
        check_file_exists(options.taxonomy_file)
        
        if options.taxa_file:
            taxa_out = open(options.taxa_file, 'w')

        # determine taxonomic resolution of named groups
        tree = dendropy.Tree.get_from_path(options.input_tree, 
                                            schema='newick', 
                                            rooting='force-rooted', 
                                            preserve_underscores=True)
        
        rank_res = defaultdict(lambda: defaultdict(int))
        for node in tree.preorder_node_iter(lambda n: n != tree.seed_node):
            if not node.label or node.is_leaf():
                continue

            _support, taxon_name, _auxiliary_info = parse_label(node.label)
            
            if taxon_name:
                lowest_rank = [x.strip() for x in taxon_name.split(';')][-1][0:3]
                for rank_prefix in Taxonomy.rank_prefixes:
                    if rank_prefix in taxon_name:
                        rank_res[rank_prefix][lowest_rank] += 1
                        if options.taxa_file:
                            taxa_out.write('%s\t%s\t%s\n' % (rank_prefix, lowest_rank, taxon_name))

        # identify any singleton taxa which are treated as having species level resolution
        for line in open(options.taxonomy_file):
            line_split = line.split('\t')
            taxonomy = line_split[1].split(';')
            
            for i, rank_prefix in enumerate(Taxonomy.rank_prefixes):
                if taxonomy[i] == rank_prefix:
                    # this taxa is undefined at the specified rank so
                    # must be the sole representative; e.g., a p__
                    # indicates a taxon that represents a novel phyla
                    rank_res[rank_prefix]['s__'] += 1
                    if options.taxa_file:
                        taxa_out.write('%s\t%s\t%s\n' % (rank_prefix, 's__', taxonomy[i]))
                    
        if options.taxa_file:
            taxa_out.close()
                      
        # write out results
        fout = open(options.output_file, 'w')
        fout.write('Category')
        for rank in Taxonomy.rank_labels[1:]:
            fout.write('\t' + rank)
        fout.write('\n')

        for i, rank_prefix in enumerate(Taxonomy.rank_prefixes[1:]):
            fout.write(Taxonomy.rank_labels[i+1])
            
            for j, r in enumerate(Taxonomy.rank_prefixes[1:]):
                if i >= j:
                    fout.write('\t' + str(rank_res[r].get(rank_prefix, 0)))
                else:
                    fout.write('\t-')
            fout.write('\n')
        fout.close()

        self.logger.info('Done.')

    def parse_options(self, options):
        """Parse user options and call the correct pipeline(s)"""

        logging.basicConfig(format='', level=logging.INFO)

        # check_dependencies(('diamond', 'ktImportText'))

        if(options.subparser_name == 'outliers'):
            self.outliers(options)
        elif(options.subparser_name == 'decorate'):
            self.decorate(options)
        elif(options.subparser_name == 'scale'):
            self.scale(options)
        elif(options.subparser_name == 'tree_diff'):
            self.tree_diff(options)
        elif(options.subparser_name == 'pull'):
            self.pull(options)
        elif(options.subparser_name == 'validate'):
            self.validate(options)
        elif(options.subparser_name == 'append'):
            self.append(options)
        elif(options.subparser_name == 'taxon_stats'):
            self.taxon_stats(options)
        elif(options.subparser_name == 'robustness_plot'):
            self.robustness_plot(options)
        elif(options.subparser_name == 'dist_plot'):
            self.dist_plot(options)
        elif(options.subparser_name == 'rd_ranks'):
            self.rd_ranks(options)
        elif(options.subparser_name == 'bl_dist'):
            self.bl_dist(options)
        elif(options.subparser_name == 'bl_optimal'):
            self.bl_optimal(options)
        elif(options.subparser_name == 'bl_decorate'):
            self.bl_decorate(options)
        elif(options.subparser_name == 'bl_table'):
            self.bl_table(options)    
        elif(options.subparser_name == 'rank_res'):
            self.rank_res(options)
        else:
            self.logger.error('  [Error] Unknown PhyloRank command: ' + options.subparser_name + '\n')
            sys.exit()

        return 0
